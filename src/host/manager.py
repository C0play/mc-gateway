import threading 
from abc import ABC, abstractmethod

from .host import BaseHost, SSHHost
from .repository import BaseHostRepository
from ..utils.logger import logger



class BaseHostManager(ABC):
    """A class for managing active hosts"""
    
    def __init__(self, hostRepo: BaseHostRepository) -> None:
        self.storage = hostRepo

    @abstractmethod
    def get(self, ip: str) -> BaseHost:
        """Get an active host with specified ip, or create a new one."""
        ...

    @abstractmethod
    def delete(self, ip: str) -> None:
        """Remove a host from active hosts."""
        ...

    def dict(self) -> dict[str, dict[str, str]]:
        """Return active hosts in JSON friendly format."""
        ...
    
    

class SSHHostManager(BaseHostManager):
    
    def __init__(self, hostRepo: BaseHostRepository) -> None:
        super().__init__(hostRepo)
        
        self.lock = threading.Lock()
        self.active_hosts: dict[str, SSHHost] = {}


    def get(self, ip: str) -> SSHHost:
        with self.lock:
            if ip in self.active_hosts:
                return self.active_hosts[ip]
            
            try:
                mac, user, path = self.storage.get(ip)
            except:
                logger.exception(f"failed to get {ip} host parameters from storage")
                raise
            else:
                host = SSHHost(ip, mac, user, path)
                self.active_hosts[ip] = host
                return host

    def add(self, ip: str, mac: str, user: str, path: str) -> None:
        """Add a new host to storage."""
        
        self.storage.add(ip, mac, user, path)

    def delete(self, ip: str) -> None:
        """Remove host from storage and active cache."""
        self.storage.remove(ip)
        
        with self.lock:
            if ip in self.active_hosts:
                del self.active_hosts[ip]
            
            

    def dict(self) -> dict[str, dict[str, str]]:
        with self.lock:
            temp = self.active_hosts.values()
        return {host.ip: host.dict() for host in temp}