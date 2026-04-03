from typing import (
    TYPE_CHECKING,
    Annotated,
    cast,
)
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

from .context import AuthContext
from ...utils.logger import logger

if TYPE_CHECKING:
    from ..data.api_key.manager import BaseKeyManager
    from ..data.user.manager import BaseUserManager
    from ..data.session.manager import SessionManager



api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", refreshUrl="/refresh", auto_error=False)



class AuthenticationManager:

    def __init__(
        self,
        key_manager: 'BaseKeyManager',
        user_manager: 'BaseUserManager',
        session_manager: 'SessionManager',
    ) -> None:
        self.keys = key_manager
        self.users = user_manager
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
            )

        user_records = None
        if api_key:
            key_record = self.keys.read_from_unhashed_key(api_key)
            user_records = self.users.read(email=key_record.user)
        elif access_token:
            if not self.sessions.validate(UUID(access_token)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="session invalid"
                )
            session_record = self.sessions.get(uuid=UUID(access_token))
            user_records = self.users.read(email=session_record.user)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="user not found"
            )
        
        user = user_records[0]
        email = cast(str, user.email)
        role = cast(str, user.role)

        return AuthContext(
            user_email = email,
            user_role = role,
            session_id = UUID(access_token) if access_token else None,
            api_key = api_key if api_key else None
        )
    

    def require_bearer(
        self,
        access_token: Annotated[str, Depends(oauth2_scheme)]
    ) -> AuthContext:
        logger.debug(access_token)
        return self.get_auth_context(None, access_token=access_token)