from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from fastapi import (
    HTTPException,
    FastAPI,
    Request,
    status
)

from ..utils.logger import logger
from ..exceptions.errors import (
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    ServiceError,
)
from .data.user.repository import SQLUserRepository
from .data.api_key.repository import SQLKeyRepository
from .data.session.repository import SQLSessionRepository
from .data.session.manager import SQLSessionManager

from .services import *
from .security import *
from .routers import *

if TYPE_CHECKING:
    from ..gateway.server import Server



class API:
    """
    Handles command execution for the gateway server.
    """

    def __init__(self, server: 'Server') -> None:
        """
        Initializes the API.

        Args:
            server: The server instance to control.
        """

        self.server = server

        self.app = FastAPI(title="mc-gateway API")
        self._register_exception_handlers()
        self._register_middleware()
        self._register_routers()


    def _register_middleware(self) -> None:

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


    def _register_routers(self) -> None:

        sessions = SQLSessionManager(SQLSessionRepository())
        keys = SQLKeyRepository()
        users = SQLUserRepository()
        roles = RoleRepository()

        authentication = AuthenticationManager(roles, keys, users, sessions)
        authorization = AuthorizationManager(authentication)

        host_service = HostService(server = self.server)
        container_service = ContainerService(server = self.server)
        player_service = WhitelistService(server = self.server)

        auth_router = AuthRouter(sessions, users, authentication).get_router()
        key_router = ApiKeyRouter(keys, authorization).get_router()
        user_router = UserRouter(roles, users, authorization).get_router()
        host_router = HostRouter(host_service, authorization).get_router()
        container_router = ContainerRouter(container_service, authorization).get_router()
        player_router = WhitelistRouter(player_service, authorization).get_router()
        system_router = SystemRouter(self.server, authorization).get_router()

        self.app.include_router(auth_router)
        self.app.include_router(key_router)
        self.app.include_router(user_router)
        self.app.include_router(host_router)
        self.app.include_router(container_router)
        self.app.include_router(player_router)
        self.app.include_router(system_router)


    def _register_exception_handlers(self) -> None:

        @self.app.exception_handler(UnauthorizedError)
        async def _unauthorized_handler(request: Request, exc: UnauthorizedError):
            logger.warning(f"API: unauthorized")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": str(exc) or "Unauthorized"},
            )

        @self.app.exception_handler(ForbiddenError)
        async def _forbidden_handler(request: Request, exc: ForbiddenError):
            logger.warning(f"API: forbidden:")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": str(exc) or "Forbidden"},
            )

        @self.app.exception_handler(NotFoundError)
        async def _not_found_handler(request: Request, exc: NotFoundError):
            logger.info(f"API: not found:")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": str(exc) or "Not found"},
            )

        @self.app.exception_handler(ConflictError)
        async def _conflict_handler(request: Request, exc: ConflictError):
            logger.info(f"API: conflict:")
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": str(exc) or "Conflict"},
            )

        @self.app.exception_handler(BadRequestError)
        async def _bad_request_handler(request: Request, exc: BadRequestError):
            logger.info(f"API: bad request:")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": str(exc) or "Bad request"},
            )

        @self.app.exception_handler(ServiceError)
        async def _service_error_handler(request: Request, exc: ServiceError):
            logger.error(f"API: service error: {exc}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

        @self.app.exception_handler(HTTPException)
        async def _http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=getattr(exc, "headers", None),
            )

        @self.app.exception_handler(Exception)
        async def _unhandled_exception_handler(request: Request, exc: Exception):
            logger.error(f"API: unhandled error while processing {request.url.path}:")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )
