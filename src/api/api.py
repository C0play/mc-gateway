from typing import TYPE_CHECKING

from fastapi import (FastAPI, Request)


from ..utils.logger import logger

from .data.user.manager import SQLUserManager
from .data.user.repository import SQLUserRepository

from .data.api_key.manager import SQLKeyManager
from .data.api_key.repository import SQLKeyRepository

from .data.session.manager import SessionManager
from .data.session.repository import SQLSessionRepository


from .services import *
from .security import *
from .routers import *


if TYPE_CHECKING:
    from ..gateway.server import Server



class API:
    """
    Handles command execution for the gateway server via the control interface.
    """

    def __init__(self, server: 'Server') -> None:
        """
        Initializes the API with a reference to the server.

        Args:
            server: The server instance to control.
        """
        self.server = server

        self.app = FastAPI(title="mc-gateway API")
        self._register()


    def _register(self) -> None:

        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            client_ip = request.client.host if request.client else "unknown"
            try:
                response = await call_next(request)
                
                if request.url.path not in ("/status", "/favicon.ico"):
                    logger.info(f"API: {client_ip} - [{response.status_code}] {request.method:<7} {request.url.path}")
                
                return response
            except Exception as e:
                logger.error(f"API: error processing {request.url.path}: {e}")
                raise e


        # ============================== ROUTERS ==============================

        sessions = SessionManager(SQLSessionRepository())
        keys = SQLKeyManager(SQLKeyRepository())
        users = SQLUserManager(
            SQLUserRepository(),
            RoleRepository()
        )

        roles = RoleRepository()
        permissions = PermissionRepository()
        authentication = AuthenticationManager(keys, users, sessions)
        authorization = AuthorizationManager(roles, permissions, authentication)

        session_service = SessionService(users = users, sessions = sessions)
        host_service = HostService(server = self.server)
        container_service = ContainerService(server = self.server)
        player_service = PlayerService(server = self.server)

        auth_router = AuthRouter(session_service, authentication).get_router()
        key_router = ApiKeyRouter(keys, authorization).get_router()
        user_router = UserRouter(users, authorization).get_router()
        host_router = HostRouter(host_service, authorization).get_router()
        container_router = ContainerRouter(container_service, authorization).get_router()
        player_router = PlayerRouter(player_service, authorization).get_router()
        system_router = SystemRouter(self.server, authorization).get_router()

        self.app.include_router(auth_router)
        self.app.include_router(key_router)
        self.app.include_router(user_router)
        self.app.include_router(host_router)
        self.app.include_router(container_router)
        self.app.include_router(player_router)
        self.app.include_router(system_router)
