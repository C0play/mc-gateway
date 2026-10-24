import threading
from abc import ABC, abstractmethod
from typing import cast

from ..api.data.models.container import ContainerConfig
from ..exceptions.errors import NotFoundError, ServiceError
from ..host.host import BaseHost, ControllerHost
from ..host.manager import BaseHostManager
from ..utils.logger import logger
from ..utils.models import Container
from .container import BaseContainer, ControllerContainer
from .repository import BaseContainerRepository


class BaseContainerManager(ABC):
    """Manages the lifecycle and active state of containers."""

    @abstractmethod
    def __init__(
        self,
        container_repo: BaseContainerRepository,
        host_manager: BaseHostManager,
        *args,
    ) -> None:

        self.storage = container_repo
        self.hosts = host_manager

    @abstractmethod
    def create(self, ip: str, config: ContainerConfig) -> Container:
        """
        Creates a new container entry and persists configuration for deferred deployment.
        The compose.yml will be deployed to the remote host on the container's first start.

        Args:
            ip: IP address of the host.
            config: Configuration for compose.yml generation.

        Returns:
            Container: The newly created container record.
        """
        ...

    @abstractmethod
    def load(self, subdomain: str) -> BaseContainer:
        """
        Returns an active container or retrieves it from storage and adds it to the active list.

        Args:
            subdomain: The subdomain of the container.

        Returns:
            BaseContainer: The initialized container instance.

        Raises:
            NotFoundError: If the container or its host cannot be found.
            ServiceError: If loading the container or host data fails.
        """
        ...

    @abstractmethod
    def unload(self, subdomain: str) -> None:
        """
        Removes a container from the active list.

        Args:
            subdomain: The subdomain of the container to unload.
        """
        ...

    @abstractmethod
    def delete(self, subdomain: str) -> None:
        """
        Removes a container from active list and storage.

        Args:
            subdomain: The subdomain of the container to delete.
        """
        ...

    @abstractmethod
    def list(self) -> list[dict[str, str]]:
        """
        Returns all active containers in a JSON-friendly format.

        Returns:
             list[dict[str, str]]: Mapping of subdomains to container details.
        """
        ...


class ControllerContainerManager(BaseContainerManager):
    def __init__(
        self,
        container_repo: BaseContainerRepository,
        host_manager: BaseHostManager,
    ) -> None:
        super().__init__(container_repo, host_manager)

        self.lock = threading.Lock()
        self.active_containers: dict[str, ControllerContainer] = {}
        self.name_to_subdomain: dict[str, str] = {}

    def create(self, ip: str, config: ContainerConfig) -> Container:

        config_payload = config.model_dump(mode="json")
        record = self.storage.create(
            ip, config.mc_port, config.rcon_port, config_payload
        )

        logger.info(
            f"Container {record.subdomain} registered for {ip}:{config.mc_port}."
        )
        return record

    def load(self, subdomain: str) -> ControllerContainer:

        with self.lock:
            if subdomain in self.active_containers:
                return self.active_containers[subdomain]

            try:
                records = self.storage.read(allow_empty=False, subdomain=subdomain)
                container_record = records[0]
            except NotFoundError:
                raise
            except Exception as e:
                logger.exception(f"failed to get container {subdomain} parameters")
                raise ServiceError(f"failed to load container {subdomain}: {e}")

            if container_record.host is None:
                raise NotFoundError("container has no host assigned")

            ip = cast(str, container_record.host.ip)
            try:
                host = self.hosts.load(ip)
                host.register_callback(on_start=lambda host: self.__cleanup(host))
            except NotFoundError:
                raise
            except Exception as e:
                raise ServiceError(
                    f"failed to load host {ip} for container {subdomain}: {e}"
                )

            container = ControllerContainer(
                subdomain,
                cast(ControllerHost, host),
                host.config.authority,
                ContainerConfig.model_validate(container_record.config),
            )

            if not container_record.initialized:
                container.deploy_callback = lambda: self.storage.update(
                    subdomain, initialized=True
                )

            self.__mark_active(container)
            return container

    def unload(self, subdomain: str) -> None:

        logger.debug(f"Removing container {subdomain} from active list")
        with self.lock:
            if subdomain not in self.active_containers:
                return

            self.active_containers[subdomain].stop()
            self.__mark_inactive(subdomain)

            inactive_hosts: set[str] = {h["ip"] for h in self.hosts.list()}
            for container in self.active_containers.values():
                inactive_hosts.discard(container.host.ip)

            for host_ip in inactive_hosts:
                self.hosts.unload(host_ip)

    def delete(self, subdomain: str) -> None:

        records = self.storage.read(allow_empty=False, subdomain=subdomain)

        if not records[0].initialized:
            logger.info(
                f"Removing container {subdomain} from storage (not initialized)"
            )
            self.storage.delete(subdomain)
            return

        container = self.load(subdomain)
        if not container.host.is_online():
            logger.info(
                f"Removal of container {subdomain} deferred until host {container.host.ip} is started again"
            )
            self.storage.update(subdomain, to_be_deleted=True)
            self.unload(subdomain)
            return

        self.storage.delete(subdomain)
        container.delete()

    def list(self) -> list[dict[str, str]]:

        with self.lock:
            temp = self.active_containers.values()
        return [container.dict() for container in temp]

    def get_by_name(self, name: str) -> ControllerContainer:
        if name not in self.name_to_subdomain:
            raise NotFoundError(f"container '{name}' is not active")
        return self.active_containers[self.name_to_subdomain[name]]

    def __mark_active(self, container: ControllerContainer):
        self.active_containers[container.subdomain] = container
        self.name_to_subdomain[f"mc_{container.mc_port}"] = container.subdomain

    def __mark_inactive(self, subdomain: str):
        port = self.active_containers[subdomain].mc_port
        del self.active_containers[subdomain]
        del self.name_to_subdomain[f"mc_{port}"]

    def __cleanup(self, host: BaseHost):
        lst = self.storage.read(allow_empty=True, to_be_deleted=True, host=host.ip)
        if len(lst) == 0:
            return

        logger.info(f"executing deferred deletions of {len(lst)} containers")
        for record in lst:
            subdomain = cast(str, record.subdomain)
            container = self.active_containers[subdomain]
            container.delete()
