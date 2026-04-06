from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

from .roles import SCOPES, RoleRepository
from .context import AuthContext
from ...exceptions import NotFoundError

if TYPE_CHECKING:
    from ..data.api_key.repository import BaseKeyRepository
    from ..data.user.repository import BaseUserRepository
    from ..data.session.manager import BaseSessionManager



api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    refreshUrl="/auth/refresh",
    auto_error=False,
    scopes=SCOPES
)



class AuthenticationManager:
    """
    Class responsible for authenticating API request. 
    Exposes the `get_auth_context` method which depends on either 
    the api_key_header or the oauth2_scheme and returns AuthContext.
    """

    def __init__(
        self,
        role_repo: RoleRepository,
        key_repo: 'BaseKeyRepository',
        user_repo: 'BaseUserRepository',
        session_manager: 'BaseSessionManager',
    ) -> None:
        self.roles = role_repo
        self.keys = key_repo
        self.users = user_repo
        self.sessions = session_manager


    def get_auth_context(
        self,
        api_key: Annotated[str | None, Depends(api_key_header)],
        access_token: Annotated[str | None, Depends(oauth2_scheme)],
    ) -> AuthContext:
        
        if not (api_key or access_token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-API-KEY or Bearer token are required",
                headers={"WWW-Authenticate": "Bearer"}
            )

        if api_key:
            try:
                key = self.keys.read_from_unhashed_key(api_key)
            except NotFoundError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(e)
                )
            user = self.users.read_one(email=key.user)

        elif access_token:
            if not self.sessions.validate(UUID(access_token)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="session expired"
                )
            session = self.sessions.get(uuid=UUID(access_token))
            user = self.users.read_one(email=session.user_email)
        
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )

        return AuthContext(
            user_email  = user.email,
            user_role   = self.roles.get(user.role),
            session_id  = UUID(access_token) if access_token else None,
            api_key     = api_key if api_key else None
        )
    

    def require_bearer(self, access_token: Annotated[str, Depends(oauth2_scheme)]) -> AuthContext:
        return self.get_auth_context(api_key=None, access_token=access_token)