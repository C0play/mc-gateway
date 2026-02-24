import threading 
from abc import ABC, abstractmethod

from .host import BaseHost, SSHHost
from .repository import BaseHostRepository
from ..utils.logger import logger



class BaseHostManager(ABC):
    """A class for managing active hosts"""
    
    def __init__(self, host_repo: BaseHostRepository) -> None:
        self.storage = host_repo

    @abstractmethod
    def load(self, ip: str) -> BaseHost:
        """
        Retrieves an active host or loads it from storage.

        Args:
            ip: The IP address of the host.

        Returns:
            BaseHost: The active host instance.

        Raises:
            KeyError: If the host cannot be found in storage.
            Exception: If loading host parameters fails.
        """
        ...

    @abstractmethod
    def unload(self, ip: str) -> None:
        """
        Removes a host from the active cache.

        Args:
            ip: The IP address of the host to unload.
        """
        ...

    @abstractmethod
    def delete(self, ip: str) -> None:
        """
        Removes a host from storage and the active cache.

        Args:
            ip: The IP address of the host to delete.
        
        Raises:
            KeyError: If the host to delete is not found in storage.
        """
        ...

    def list(self) -> list[dict[str, str]]:
        """
        Returns a dictionary representation of all active hosts.

        Returns:
            list[dict[str, str]]: A mapping of IP addresses to host details.
        """
        ...
    
    

class SSHHostManager(BaseHostManager):
    """
    Manages active SSHHost instances.
    """
    
    def __init__(self, host_repo: BaseHostRepository) -> None:
        super().__init__(host_repo)
        
        self.lock = threading.Lock()
        self.active_hosts: dict[str, SSHHost] = {}


    def load(self, ip: str) -> SSHHost:
        with self.lock:
            if ip in self.active_hosts:
                return self.active_hosts[ip]
            
            try:
                mac, user, path = self.storage.read(ip)
            except:
                logger.exception(f"failed to get {ip} host parameters from storage")
                raise
            else:
                host = SSHHost(ip, mac, user, path)
                self.active_hosts[ip] = host
                return host


    def unload(self, ip: str) -> None:
        
        logger.debug(f"Removing host {ip} from active list")
        with self.lock:
            if ip in self.active_hosts:
                del self.active_hosts[ip]
    
    
    def delete(self, ip: str) -> None:
        
        self.unload(ip)
        logger.debug(f"Removing host {ip} from storage")
        self.storage.delete(ip)
            


    def list(self) -> list[dict[str, str]]:
        with self.lock:
            temp = self.active_hosts.values()
        return [host.dict() for host in temp]