import time
import threading
from abc import ABC, abstractmethod

from ..config.config import ShutdownConfig

from ..container.container import BaseContainer
from ..container.manager import ContainerManager

from ..gateway.client import Client

from .session import Session

from ..utils.logger import logger


class BaseSessionManager(ABC):
    """A base class for managing sessions"""

    @abstractmethod
    def __init__(self, containerManager: ContainerManager, shutdownConfig: ShutdownConfig) -> None:
        self.containers = containerManager
        self.cfg = shutdownConfig

    @abstractmethod
    def open(self, client: Client, subdomain: str) -> Session:
        """
        Creates a new session for the client connected to the specified subdomain.

        Args:
            client: The client requesting valid session.
            subdomain: The target container's subdomain.

        Returns:
            Session: The created session object.

        Raises:
            KeyError: If the client already has a session.
            Exception: If loading the container fails.
        """
        ...

    @abstractmethod
    def interrupt(self, reason: str, subdomain: str = "", ip: str = "") -> None:
        """
        Force closes all client sessions matching the criteria.
        
        Args:
             reason: The disconnect reason sent to clients.
             subdomain: (Optional) Filter by container subdomain.
             ip: (Optional) Filter by host IP.

        Raises:
             ValueError: If neither subdomain nor ip is provided.
        """
        ...
    
    @abstractmethod
    def close(self, client: Client) -> None:
        """
        Removes a client's session.

        Args:
             client: The client to remove.

        Raises:
             KeyError: If the client has no open session.
        """
        ...
    
    @abstractmethod
    def autoshutdown(self) -> None:
        """
        Periodically checks for idle containers and stops them based on configuration.
        """
        ...


class SessionManager(BaseSessionManager):
    
    def __init__(self, containerManager: ContainerManager, shutdownConfig: ShutdownConfig) -> None:
        self.containers = containerManager
        self.cfg = shutdownConfig

        self.sessions_lock = threading.Lock()
        self.sessions: dict[Client, Session] = {}


    def open(self, client: Client, subdomain: str) -> Session:

        with self.sessions_lock:
            if client in self.sessions:
                raise KeyError(f"{client} already has a session")
        
        try:
            container = self.containers.load(subdomain)
        except:
            logger.exception(f"failed to get {subdomain} container from manager")
            raise
        else:
            session = Session(client, container)
            with self.sessions_lock:
                self.sessions[client] = session
            
            logger.debug(f"created {container} for {client}")
            return session


    def interrupt(self, reason: str, subdomain: str = "", ip: str = "") -> None:

        if not (subdomain or ip):
            logger.error(f"ip and subdomain")
            raise ValueError(f"one of [ip, subdomain] have to be specified")
        
        clients = []
        with self.sessions_lock:
            if subdomain:
                clients = [s.client for s in self.sessions.values() if s.container.subdomain == subdomain]
            elif ip:
                clients = [s.client for s in self.sessions.values() if s.container.host.ip == ip]

        logger.debug(f"Interrupting sessions of {clients} from {ip}{subdomain}")
        for client in clients:
            self.sessions[client].server_disconnect(reason)


    def close(self, client: Client) -> None:

        with self.sessions_lock:
            if client not in self.sessions:
                raise KeyError(f"has no open sessions")
        
            del self.sessions[client]


    def autoshutdown(self) -> None:
        
        container_timeout = max(120, int(self.cfg.container_idle_timeout))
        check_interval = max(15, min(60, container_timeout // 3))

        container_idle_since: dict[BaseContainer, float] = {}

        while True:
            time.sleep(check_interval)
            now = time.time()
            with self.containers.lock:
                containers = self.containers.active_containers.values()

            with self.sessions_lock:
                sessions = [session for session in self.sessions.values()]

            container_clients: dict[BaseContainer, int] = {}
            for container in containers:
                container_clients.setdefault(container, 0)

            for session in sessions:
                if session.container not in container_clients:
                    continue
                clients = container_clients[session.container]
                container_clients[session.container] = clients + 1

            for container, clients in container_clients.items():
                logger.debug(f"{container}: {now - container_idle_since.setdefault(container, now)}")
                
                if clients > 0:
                    container_idle_since.pop(container, None)
                    continue
                
                idle_for = now - container_idle_since.setdefault(container, now)
                if idle_for < container_timeout:
                    continue
                
                logger.info(f"{container} idle for {int(idle_for)}s, stopping.")
                try:
                    self.containers.unload(container.subdomain)
                    container_idle_since.pop(container, None)
                except Exception:
                    logger.exception(f"failed to stop {container}")
                    

    def dict(self) -> list[dict[str, str]]:

        with self.sessions_lock:
            temp = self.sessions.items()
        return [{
                "client": client.__str__(),
                "container": session.container.__str__(),
            } for client, session in temp
        ]