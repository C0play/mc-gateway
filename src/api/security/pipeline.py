from dataclasses import dataclass
from enum import Enum
from uuid import UUID
from typing import (
    TYPE_CHECKING,
    Annotated,
    Callable,
    cast,
    Any,
)
import datetime

from fastapi import Depends, HTTPException, Request
from fastapi import status as code
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

from ...exceptions.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    UnauthorizedError,
)

if TYPE_CHECKING:
    from ..data.api_key.manager import SQLKeyManager
    from ..data.session.manager import SessionManager
    from ...utils.models import Session
    from ..data.user.manager import SQLUserManager
    from ..data.user.roles import Permission
    from ...container.repository import BaseContainerRepository

class AuthMode(str, Enum):
    BEARER = "bearer"
    API_KEY = "api_key"


@dataclass(frozen=True)
class AccessContext:
    email: str
    mode: AuthMode
    session_id: UUID | None = None
    api_key: str | None = None


OwnershipValidator = Callable[..., None]

class AccessPipeline:
    """Centralized access pipeline for auth -> ownership -> permissions."""

    def __init__(
        self,
        users: 'SQLUserManager',
        keys: 'SQLKeyManager',
        sessions: 'SessionManager',
        container_repo: 'BaseContainerRepository | None' = None,
    ) -> None:
        
        self.users = users
        self.keys = keys
        self.sessions = sessions
        self.container_storage = container_repo

        self.api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


    def container_ownership_validator(self, *, path_param: str = "subdomain") -> OwnershipValidator:
        def _validator(email: str, request: Request) -> None:
            if self.container_storage is None:
                raise ServiceError("container storage is not configured")

            resource_id = str(request.path_params.get(path_param, ""))
            if not resource_id:
                raise BadRequestError(f"missing path param: {path_param}")

            records = self.container_storage.read(subdomain=resource_id)
            if not records:
                raise NotFoundError(f"container {resource_id} does not exist")

            owner = records[0].owner
            owner_email = str(owner.email) if owner is not None else ""
            if owner_email != email:
                raise ForbiddenError(f"container {resource_id} does not belong to {email}")

        return _validator


    def key_ownership_validator(self, *, path_param: str = "name") -> OwnershipValidator:
        def _validator(email: str, request: Request) -> None:
            
            resource_id = str(request.path_params.get(path_param, ""))
            if not resource_id:
                raise BadRequestError(f"missing path param: {path_param}")

            records = self.keys.read(name=resource_id, user=email)
            if not records:
                raise NotFoundError(f"key {resource_id} does not exist")

        return _validator


    def guard(self, *,
        auth_modes: tuple[AuthMode, ...],
        permissions: tuple['Permission', ...] = (),
        ownership_validator: OwnershipValidator | None = None,
    ) -> Callable[..., AccessContext]:
        def _dep(
            request: Request,
            bearer_token: Annotated[str | None, Depends(self.oauth2_scheme)],
            api_key: Annotated[str | None, Depends(self.api_key_header)],
        ) -> AccessContext:
            try:
                context = self._authenticate(auth_modes, bearer_token, api_key)

                if ownership_validator is not None:
                    ownership_validator(context.email, request)

                for permission in permissions:
                    if not self.users.validate_permission(context.email, permission.name):
                        raise ForbiddenError(f"Missing permission: {permission.name}")

                return context
            except HTTPException:
                raise
            except Exception as exc:
                raise self._to_http_exception(exc)

        return _dep


    def _authenticate(
        self,
        auth_modes: tuple[AuthMode, ...],
        bearer_token: str | None,
        api_key: str | None,
    ) -> AccessContext:
        if AuthMode.BEARER in auth_modes and bearer_token:
            return self._authenticate_bearer(bearer_token)

        if AuthMode.API_KEY in auth_modes and api_key:
            return self._authenticate_api_key(api_key)

        expected = " or ".join(mode.value for mode in auth_modes)
        raise UnauthorizedError(f"Missing credentials: expected {expected}")


    def _authenticate_bearer(self, token: str) -> AccessContext:
        try:
            session_uuid = UUID(token)
        except ValueError as exc:
            raise UnauthorizedError("Invalid bearer token") from exc

        if not self.sessions.validate(session_uuid):
            raise UnauthorizedError("Session invalid or expired")

        session = self.sessions.get(uuid=session_uuid)
        
        self._extend_bearer_ttl(session)

        return AccessContext(
            email=str(session.user.email),
            mode=AuthMode.BEARER,
            session_id=session_uuid,
        )


    def _extend_bearer_ttl(self, session: 'Session') -> None:
        valid_until = cast(datetime.datetime, session.valid_until)
        created_at = cast(datetime.datetime, session.created_at)
        self.sessions.extend(
            cast(UUID, session.id),
            created_at,
            valid_until,
        )


    def _authenticate_api_key(self, api_key: str) -> AccessContext:
        record = self.keys.read_from_unhashed_key(api_key)
        if not bool(record.active):
            raise UnauthorizedError("API key is inactive")
        return AccessContext(
            email=str(record.user.email),
            mode=AuthMode.API_KEY,
            api_key=api_key,
        )


    @staticmethod
    def _to_http_exception(exc: Exception) -> HTTPException:
        if isinstance(exc, UnauthorizedError):
            return HTTPException(
                status_code=code.HTTP_401_UNAUTHORIZED,
                detail=str(exc) or "Unauthorized",
            )
        if isinstance(exc, ForbiddenError):
            return HTTPException(
                status_code=code.HTTP_403_FORBIDDEN,
                detail=str(exc) or "Forbidden",
            )
        if isinstance(exc, NotFoundError):
            return HTTPException(
                status_code=code.HTTP_404_NOT_FOUND,
                detail=str(exc) or "Not found",
            )
        if isinstance(exc, ConflictError):
            return HTTPException(
                status_code=code.HTTP_409_CONFLICT,
                detail=str(exc) or "Conflict",
            )
        if isinstance(exc, BadRequestError):
            return HTTPException(
                status_code=code.HTTP_400_BAD_REQUEST,
                detail=str(exc) or "Bad request",
            )
        if isinstance(exc, ServiceError):
            return HTTPException(
                status_code=code.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )
        return HTTPException(
            status_code=code.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )