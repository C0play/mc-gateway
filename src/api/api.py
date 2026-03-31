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

from .data.user.roles import RoleRepository
from .data.user.manager import SQLUserManager
from .data.user.repository import SQLUserRepository

from .data.api_keys.repository import SQLKeyRepository
from .data.api_keys.manager import SQLKeyManager

from .data.session.manager import SessionManager
from .data.session.repository import SQLSessionRepository

from .security import AccessPipeline
from .security.guards import build_access_guards

from .endpoints.auth import build_auth_router
from .endpoints.system import build_system_admin_router
from .endpoints.players import build_player_admin_router, build_player_me_router
from .endpoints.containers import build_container_admin_router, build_container_me_router
from .endpoints.hosts import build_host_admin_router
from .endpoints.me import build_me_router

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
        
        self.access = AccessPipeline(
            users=self.users,
            keys=self.keys,
            sessions=self.sessions,
            container_repo=self.server._sessions.containers.storage
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
        guards = build_access_guards(self.access)

        # ================================ AUTH ===============================

        @self.app.middleware("http")
        async def authenticate_requset(request: Request, call_next):
            
            ...

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

        # PUBLIC
        auth_router = build_auth_router(self.user_service, self.session_service)
        

        # ADMIN
        admin_router = APIRouter(prefix="/admin")
        
        system_admin_router = build_system_admin_router(
            self.server,
            guards.require_view_status,
            guards.require_stop_server,
        )
        
        player_admin_router = build_player_admin_router(
            self.player_service,
            guards.require_manage_whitelists
        )
        
        container_admin_router = build_container_admin_router(
            self.container_service,
            guards.require_manage_containers
        )
        
        host_admin_router = build_host_admin_router(
            self.host_service,
            guards.require_manage_hosts
        )
        
        admin_router.include_router(system_admin_router)
        admin_router.include_router(player_admin_router)
        admin_router.include_router(container_admin_router)
        admin_router.include_router(host_admin_router)


        # USER
        me_router = build_me_router(
            self.session_service,
            self.api_key_service,
            guards.require_session,
            guards.require_user_manage_own_apikeys,
        )

        container_me_router = build_container_me_router(
            self.container_service,
            guards.require_user_manage_own_containers,
            guards.require_session,
        )

        player_me_router = build_player_me_router(
            self.player_service,
            guards.require_user_manage_own_containers,
        )

        me_router.include_router(container_me_router)
        me_router.include_router(player_me_router)

        # ============================== MAIN APP ==============================

        self.app.include_router(auth_router)
        self.app.include_router(admin_router)
        self.app.include_router(me_router)