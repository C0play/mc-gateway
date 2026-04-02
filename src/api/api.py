from typing import TYPE_CHECKING

from fastapi import (
    FastAPI,
    Request,
    APIRouter,
)

from ..utils.logger import logger

from .services.player import PlayerService
from .services.container import ContainerService
from .services.host import HostService
from .services.user import UserService
from .services.session import SessionService
from .services.api_key import ApiKeyService

from .security.roles import RoleRepository
from .data.user.manager import SQLUserManager
from .data.user.repository import SQLUserRepository

from .data.api_key.repository import SQLKeyRepository
from .data.api_key.manager import SQLKeyManager

from .data.session.manager import SessionManager
from .data.session.repository import SQLSessionRepository


from .endpoints.auth import auth_router
from .endpoints.system import build_system_admin_router
from .endpoints.players import build_player_admin_router, build_player_me_router
from .endpoints.containers import container_router, build_container_me_router
from .endpoints.hosts import build_host_admin_router
from .endpoints.keys import build_me_router

if TYPE_CHECKING:
    from ..gateway.server import Server


# ======================================== FastAPI ========================================

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

        self.player_service = PlayerService(server=self.server)
        self.container_service = ContainerService(server=self.server)
        self.host_service = HostService(server=self.server)
        
        self.keys = SQLKeyManager(
            SQLKeyRepository()
        )

        self.users = SQLUserManager(
            SQLUserRepository(),
            RoleRepository()
        )

        self.sessions = SessionManager(
            SQLSessionRepository()
        )
        
        self.user_service = UserService(
            users=self.users,
        )
        self.session_service = SessionService(
            users=self.users,
            sessions=self.sessions,
        )
        self.api_key_service = ApiKeyService(
            keys=self.keys,
        )

        self.app = FastAPI(title="mc-gateway API")
        
        self._register()


    def _register(self) -> None:

        # ============================== LOGGING ==============================

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

        router_public = APIRouter(
           prefix="/public",
           tags=["Public"]
        )

        router_protected = APIRouter(
            prefix=" "
        )