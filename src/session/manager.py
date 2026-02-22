import time
import threading

from ..config.config import ShutdownConfig

from ..container.container import BaseContainer
from ..container.manager import ContainerManager
from ..host.host import BaseHost

from ..gateway.client import Client

from .session import Session
from ..utils.logger import logger


class SessionManager():
    
    def __init__(self, containerManager: ContainerManager, shutdownConfig: ShutdownConfig) -> None:
        self.containers = containerManager
        self.cfg = shutdownConfig

        self.sessions_lock = threading.Lock()
        self.sessions: dict[Client, Session] = {}


    def open(self, client: Client, subdomain: str) -> Session:
        """Create a new session for the client."""

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
        """Force close all client sessions for a container even if it's still open"""

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
        """Delete a client's session after they already disconnected"""

        with self.sessions_lock:
            if client not in self.sessions:
                raise KeyError(f"has no open sessions")
        
            del self.sessions[client]


    def autoshutdown(self) -> None:
        """Shutdown all containers that didn't have an active session in a provided time frame."""
        
        container_timeout = max(120, int(self.cfg.container_idle_timeout))
        check_interval = max(15, min(60, container_timeout // 3))

        container_idle_since: dict[BaseContainer, float] = {}

        while True:
            time.sleep(check_interval)
            now = time.time()

            with self.sessions_lock:
                snapshot = [session for session in self.sessions.values()]

            containers: dict[BaseContainer, int] = {}
            for session in snapshot:
                clients = containers.setdefault(session.container, 0)
                containers[session.container] = clients + 1

            for container, clients in containers.items():
                if clients > 0:
                    continue

                idle_for = now - container_idle_since.setdefault(container, now)
                if idle_for < container_timeout:
                    continue
                
                logger.info(f"{container} idle for {int(idle_for)}s, stopping.")
                try:
                    container.stop()
                    container_idle_since.pop(container, None)
                except Exception:
                    logger.exception(f"failed to stop {container}")
                    

    def dict(self) -> dict[str, dict[str, str]]:
        """Return all active sessions in JSON friendly format."""

        with self.sessions_lock:
            temp = self.sessions.items()
        return {client.__str__(): session.container.dict() for client, session in temp}