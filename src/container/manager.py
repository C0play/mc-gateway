import threading
from abc import ABC, abstractmethod

from .repository import BaseContainerRepository
from .container import BaseContainer, SSHContainer
from ..host.manager import BaseHostManager
from ..utils.logger import logger


class BaseContainerManager(ABC):
    """Manages the lifecycle and active state of containers."""

    @abstractmethod
    def __init__(self, container_repo: BaseContainerRepository, host_manager: BaseHostManager) -> None:
        self.storage = container_repo
        self.host_manager = host_manager

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
        self.storage = container_repo
        self.hosts = host_manager

        self.lock = threading.Lock()
        self.active_containers: dict[str, SSHContainer] = {}

    
    def load(self, subdomain: str) -> SSHContainer:

        with self.lock:
            if subdomain in self.active_containers:
                return self.active_containers[subdomain]
            
            try:
                ip, port = self.storage.read(subdomain)
            except Exception:
                logger.exception(f"failed to get container {subdomain} parameters")
                raise
            
            # Get associated host
            try:
                host = self.hosts.load(ip)
            except Exception:
                raise RuntimeError(f"Host {ip} for container {subdomain} not found")

            container = SSHContainer(subdomain, port, host)
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

        logger.debug(f"Removing container {subdomain} from storage")
        self.unload(subdomain)
        self.storage.delete(subdomain)
    
    
    def list(self) -> list[dict[str, str]]:

        with self.lock:
            temp = self.active_containers.values()
        return [container.dict() for container in temp]