import secrets
import threading
from abc import ABC, abstractmethod
from typing import cast

from .repository import BaseContainerRepository
from .container import BaseContainer, SSHContainer
from ..host.manager import BaseHostManager
from ..host.host import BaseHost, SSHHost
from ..utils.composegen import generate_compose, ComposeConfig
from ..utils.models import Container as ContainerRecord
from ..utils.logger import logger
from ..utils.crypto import CryptoProvider


class BaseContainerManager(ABC):
    """Manages the lifecycle and active state of containers."""

    @abstractmethod
    def __init__(self, container_repo: BaseContainerRepository, host_manager: BaseHostManager) -> None:
        self.storage = container_repo
        self.hosts = host_manager


    @abstractmethod
    def create(self, ip: str, mc_port: int, rcon_port: int, config: ComposeConfig) -> ContainerRecord:
        """
        Creates a new container entry and persists configuration for deferred deployment.
        The compose.yml will be deployed to the remote host on the container's first start.

        Args:
            ip: IP address of the host.
            mc_port: Minecraft port for the new container.
            rcon_port: RCON port for the new container.
            config: Configuration for compose.yml generation.

        Returns:
            ContainerRecord: The newly created container record.
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
            KeyError: If the container parameters cannot be found in storage.
            RuntimeError: If the associated host cannot be found.
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


class ContainerManager(BaseContainerManager):

    def __init__(self, container_repo: BaseContainerRepository, host_manager: BaseHostManager) -> None:
        super().__init__(container_repo, host_manager)

        self.lock = threading.Lock()
        self.active_containers: dict[str, SSHContainer] = {}

    
    def create(self, ip: str, mc_port: int, rcon_port: int, config: ComposeConfig) -> ContainerRecord:
        """
        Persists container record with serialized config and encrypted RCON password.
        Does NOT require host to be online.
        """
        raw_password = secrets.token_urlsafe(24)
        encrypted_password = CryptoProvider.encrypt(raw_password)
        
        config_json = config.model_dump_json()
        record = self.storage.create(ip, mc_port, rcon_port, encrypted_password, config_json)
        
        logger.info(f"Container {record.subdomain} registered on {ip}:{mc_port}.")
        return record


    def load(self, subdomain: str) -> SSHContainer:

        with self.lock:
            if subdomain in self.active_containers:
                return self.active_containers[subdomain]
            
            try:
                records = self.storage.read(subdomain=subdomain)
            except Exception:
                logger.exception(f"failed to get container {subdomain} parameters")
                raise
            if not records:
                raise KeyError(f"container {subdomain} not found")
            record = records[0]
            
            ip = cast(str, record.host.ip)
            mc_port = cast(int, record.mc_port)
            rcon_port = cast(int, record.rcon_port)
            
            # Decrypt the RCON password at runtime
            encrypted_pwd = cast(str, record.rcon_password)
            rcon_password = CryptoProvider.decrypt(encrypted_pwd)

            # Get associated host
            try:
                host = self.hosts.load(ip)
                host.register_callback(
                    on_start=lambda host: self._cleanup_pending_deletions(host)
                )
            except Exception:
                raise RuntimeError(f"Host {ip} for container {subdomain} not found")

            deploy = None
            if not record.initialized:
                cfg = generate_compose(
                    mc_port,
                    rcon_port,
                    rcon_password,
                    ComposeConfig.model_validate_json(cast(str, record.config))
                )
                def _deploy(mc_port=mc_port, cfg=cfg, subdomain=subdomain):
                    host.deploy(mc_port, cfg)
                    self.storage.update(subdomain, initialized=True)
                deploy = _deploy

            container = SSHContainer(
                subdomain, cast(SSHHost, host), mc_port,
                rcon_port, rcon_password, deploy
            )
            self.active_containers[subdomain] = container
            return container
        

    def unload(self, subdomain: str) -> None:

        logger.debug(f"Removing container {subdomain} from active list")
        with self.lock:
            if subdomain not in self.active_containers:
                return
            
            self.active_containers[subdomain].stop()
            del self.active_containers[subdomain]
            
            inactive_hosts: set[str] = set([h["ip"] for h in self.hosts.list()])
            for container in self.active_containers.values():
                inactive_hosts.discard(container.host.ip)
            
            for host_ip in inactive_hosts:
                self.hosts.unload(host_ip)
            
    
    def delete(self, subdomain: str) -> None:

        records = self.storage.read(subdomain=subdomain)
        if not records:
            raise KeyError(f"container {subdomain} does not exist")
        
        if not records[0].initialized:
            logger.info(f"Removing container {subdomain} from storage (not initialized)")
            self.storage.delete(subdomain)
            return

        container = self.load(subdomain)
        if not container.host.is_online():
            try:
                logger.info(f"Removal of container {subdomain} deferred until "
                            +f"host {container.host.ip} is started again")
                self.storage.update(subdomain, to_be_deleted=True)
            except Exception as e:
                raise RuntimeError(f"failed to set {subdomain} to be deleted: {e}")
            self.unload(subdomain)
            return
        
        self._delete_from_online_host(subdomain, container)

    
    def _delete_from_online_host(self, subdomain: str, container: SSHContainer) -> None:
        """Stops a running container, then removes its files and storage record."""
        try:
            logger.info(f"Removing container {subdomain} from active list")
            container.stop()
            with self.lock:
                self.active_containers.pop(subdomain, None)
        except Exception as e:
            raise RuntimeError(f"failed to stop {subdomain} before deletion: {e}")
        self._delete_container_files(subdomain, container.host, container.mc_port)


    def _delete_container_files(self, subdomain: str, host: BaseHost, mc_port: int) -> None:
        """Removes a container's directory and storage record."""
        try:
            logger.info(f"Removing container {subdomain} from disk")
            host.remove(mc_port)
        except Exception as e:
            raise RuntimeError(f"failed to delete directory of {subdomain}: {e}")
        try:
            logger.info(f"Removing container {subdomain} from storage")
            self.storage.delete(subdomain)
        except Exception as e:
            raise RuntimeError(f"failed to remove {subdomain} from storage: {e}")

    
    def _cleanup_pending_deletions(self, host: BaseHost) -> None:
        lst = self.storage.read(to_be_deleted=True, host=host.ip)
        if len(lst) == 0:
            return

        logger.info(f"executing deferred deletions of {len(lst)} containers")
        for record in lst:
            subdomain = cast(str, record.subdomain)
            mc_port = cast(int, record.mc_port)
            self._delete_container_files(subdomain, host, mc_port)


    def list(self) -> list[dict[str, str]]:

        with self.lock:
            temp = self.active_containers.values()
        return [container.dict() for container in temp]