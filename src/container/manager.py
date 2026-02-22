import threading
from abc import ABC, abstractmethod

from .repository import BaseContainerRepository
from .container import BaseContainer, SSHContainer
from ..host.manager import BaseHostManager
from ..utils.logger import logger


class BaseContainerManager(ABC):
    """Manages the lifecycle and active state of containers."""

    @abstractmethod
    def __init__(self, containerRepo: BaseContainerRepository, hostManager: BaseHostManager) -> None:
        self.storage = containerRepo
        self.hostManager = hostManager

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
    def dict(self) -> dict[str, dict[str, str]]:
        """
        Returns all active containers in a JSON-friendly format.

        Returns:
             dict[str, dict[str, str]]: Mapping of subdomains to container details.
        """
        ...


class ContainerManager(BaseContainerManager):

    def __init__(self, containerRepo: BaseContainerRepository, hostManager: BaseHostManager) -> None:
        self.storage = containerRepo
        self.hostManager = hostManager

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
                host = self.hostManager.load(ip)
            except Exception:
                raise RuntimeError(f"Host {ip} for container {subdomain} not found")

            container = SSHContainer(subdomain, port, host)
            self.active_containers[subdomain] = container
            return container
        

    def unload(self, subdomain: str) -> None:

        logger.debug(f"Removing container {subdomain} from active list")
        with self.lock:
            if subdomain in self.active_containers:
                del self.active_containers[subdomain]
    
    def delete(self, subdomain: str) -> None:

        logger.debug(f"Removing container {subdomain} from storage")
        self.unload(subdomain)
        self.storage.delete(subdomain)
    
    
    def dict(self) -> dict[str, dict[str, str]]:

        with self.lock:
            temp = self.active_containers.items()
        return {subdomain: container.dict() for subdomain, container in temp}