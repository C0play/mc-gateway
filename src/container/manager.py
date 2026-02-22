import threading

from .repository import BaseContainerRepository
from .container import SSHContainer
from ..host.manager import BaseHostManager
from ..utils.logger import logger



class ContainerManager():
    """A class for managing active containers"""

    def __init__(self, containerRepo: BaseContainerRepository, hostManager: BaseHostManager) -> None:
        self.storage = containerRepo
        self.hostManager = hostManager

        self.lock = threading.Lock()
        self.active_containers: dict[str, SSHContainer] = {}

    
    def load(self, subdomain: str) -> SSHContainer:
        """Return an active container or retrieve it from storage, and add to actives."""

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
        """Remove a container from actives."""

        logger.debug(f"Removing container {subdomain} from active list")
        with self.lock:
            if subdomain in self.active_containers:
                del self.active_containers[subdomain]
    
    def delete(self, subdomain: str) -> None:
        """Remove a container from actives and storage."""

        logger.debug(f"Removing container {subdomain} from storage")
        self.unload(subdomain)
        self.storage.delete(subdomain)
    
    
    def dict(self) -> dict[str, dict[str, str]]:
        """Return all active containers in JSON friendly format."""

        with self.lock:
            temp = self.active_containers.items()
        return {subdomain: container.dict() for subdomain, container in temp}