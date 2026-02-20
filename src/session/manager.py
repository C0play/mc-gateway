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

        self.hosts_lock = threading.Lock()
        self.hosts: dict[BaseHost, dict[BaseContainer, int]] = {} # host -> container -> clients
        
        self.sessions_lock = threading.Lock()
        self.sessions: dict[Client, Session] = {}


    def create(self, client: Client, subdomain: str) -> Session:
        """Create a new session for the client."""

        with self.sessions_lock:
            if client in self.sessions:
                raise KeyError(f"{client} already has a session")
        
        try:
            container = self.containers.get(subdomain)
        except:
            logger.exception(f"failed to get {subdomain} container from manager")
            raise
        else:
            session = Session(client, container)
            with self.sessions_lock:
                self.sessions[client] = session
            
            with self.hosts_lock:
                if container.host not in self.hosts:
                    self.hosts[container.host] = {container: 0}
                
                self.hosts[container.host][container] += 1
                
            logger.debug(f"created {container} for {client}")
            return session
    

    def delete(self, client: Client) -> None:
        """Delete a client's session."""

        with self.sessions_lock:
            if client not in self.sessions:
                raise KeyError(f"client {client} has no open sessions")
        
        with self.sessions_lock, self.hosts_lock:
            self.hosts[self.sessions[client].container.host][self.sessions[client].container] -= 1
            del self.sessions[client]

    
    def autoshutdown(self) -> None:
        """Shutdown all containers that didn't have an active session in a provided time frame."""
        
        container_t = max(90, int(self.cfg.container_idle_timeout))
        check_interval = max(15, min(60, container_t // 3))

        container_idle_since: dict[BaseContainer, float] = {}

        while True:
            time.sleep(check_interval)
            now = time.time()

            with self.hosts_lock:
                snapshot = {h: dict(c) for h, c in self.hosts.items()}

            # Containers: track idle and stop after threshold
            for host, containers in snapshot.items():
                for container, clients in containers.items():
                    if clients == 0:
                        idle_for = now - container_idle_since.setdefault(container, now)
                        
                        if idle_for < container_t:
                            continue
                        
                        with self.hosts_lock:
                            still_zero = self.hosts.get(host, {}).get(container, 0) == 0
                        
                        if still_zero:
                            try:
                                logger.info(f"{container} idle for {int(idle_for)}s, stopping.")
                                container.stop()
                            except Exception:
                                logger.exception(f"failed to stop {container}")
                        container_idle_since.pop(container, None)
                    
                    else:
                        container_idle_since.pop(container, None)


    def dict(self) -> dict[str, dict[str, str]]:
        """Return all active sessions in JSON friendly format."""

        with self.sessions_lock:
            temp = self.sessions.items()
        return {client.__str__(): session.container.dict() for client, session in temp}