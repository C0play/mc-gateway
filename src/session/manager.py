import time
import threading
from abc import ABC, abstractmethod

from ..config.config import ShutdownConfig

from ..container.container import BaseContainer
from ..container.manager import ContainerManager

from ..gateway.client import Client

from .session import Session

from ..utils.logger import logger
from ..exceptions.errors import BadRequestError, ConflictError, NotFoundError, ServiceError


class BaseSessionManager(ABC):
    """A base class for managing sessions"""

    @abstractmethod
    def __init__(self, container_manager: ContainerManager, shutdown_config: ShutdownConfig) -> None:
        self.containers = container_manager
        self.cfg = shutdown_config

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
            ConflictError: If the client already has a session or container is marked for deletion.
            NotFoundError: If the target container does not exist.
            ServiceError: If loading the container fails unexpectedly.
        """
        ...

    @abstractmethod
    def interrupt(self, reason: str, username: str = "", subdomain: str = "", ip: str = "") -> None:
        """
        Force closes all client sessions matching the criteria.
        
        Args:
            reason: The disconnect reason sent to clients.
            username: (Optional) Kick specific user.
            subdomain: (Optional) Filter by container subdomain.
            ip: (Optional) Filter by host IP.

        Raises:
            BadRequestError: If neither subdomain nor ip is provided.
        """
        ...
    
    @abstractmethod
    def close(self, client: Client) -> None:
        """
        Removes a client's session.

        Args:
            client: The client to remove.

        Raises:
            NotFoundError: If the client has no open session.
        """
        ...
    
    @abstractmethod
    def autoshutdown(self) -> None:
        """
        Periodically checks for idle containers and stops them based on configuration.
        """
        ...


class SessionManager(BaseSessionManager):
    
    def __init__(self, container_manager: ContainerManager, shutdown_config: ShutdownConfig) -> None:
        self.containers = container_manager
        self.cfg = shutdown_config

        self.sessions_lock = threading.Lock()
        self.sessions: dict[Client, Session] = {}


    def open(self, client: Client, subdomain: str) -> Session:

        with self.sessions_lock:
            if client in self.sessions:
                raise ConflictError(f"{client} already has a session")
        
        if self.containers.storage.read(subdomain=subdomain, to_be_deleted=True):
            raise ConflictError(f"container {subdomain} is marked for deletion")
        
        try:
            container = self.containers.load(subdomain)
        except NotFoundError:
            raise
        except Exception as e:
            logger.exception(f"failed to get {subdomain} container from manager: {e}")
            raise ServiceError(f"failed to open session for {subdomain}: {e}")
        else:
            session = Session(client, container)
            with self.sessions_lock:
                self.sessions[client] = session
            
            logger.debug(f"created {container} for {client}")
            return session


    def interrupt(self, reason: str = "You were kicked", username: str = "", subdomain: str = "", ip: str = "") -> None:

        if not (username or subdomain or ip):
            raise BadRequestError("one of [username, subdomain, ip] has to be specified")
        
        clients = []
        with self.sessions_lock:
            snapshot = self.sessions
        
        if username:
            clients = list(filter(lambda c: c.username == username, list(snapshot.keys())))
            logger.debug(f"Interrupting session of {username}")
        elif subdomain:
            clients = [s.client for s in snapshot.values() if s.container.subdomain == subdomain]
            logger.debug(f"Interrupting sessions of {len(clients)} clients from {subdomain}")
        elif ip:
            clients = [s.client for s in snapshot.values() if s.container.host.ip == ip]
            logger.debug(f"Interrupting sessions of {len(clients)} clients from {ip}")

        for client in clients:
            snapshot[client].server_disconnect(reason)


    def close(self, client: Client) -> None:

        with self.sessions_lock:
            if client not in self.sessions:
                raise NotFoundError("session does not exist")
        
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
                sessions = self.sessions.values()

            container_clients: dict[BaseContainer, int] = {}
            for container in containers:
                container_clients.setdefault(container, 0)

            for session in sessions:
                if session.container not in container_clients:
                    continue
                clients = container_clients[session.container]
                container_clients[session.container] = clients + 1

            for container, clients in container_clients.items():
                
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
                    

    def list(self) -> list[dict[str, str]]:

        with self.sessions_lock:
            temp = self.sessions.values()
        return [session.dict() for session in temp]