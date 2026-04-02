from typing import (
    Annotated,
    cast,
)
from uuid import UUID

from fastapi import (
    Depends,
    HTTPException,
    status
)
from fastapi.security import (
    APIKeyHeader,
    OAuth2PasswordBearer
)

from .context import AuthContext
from ...exceptions import UnauthorizedError
from ..data.api_key.manager import BaseKeyManager
from ..data.user.manager import BaseUserManager
from ..data.session.manager import SessionManager


api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", refreshUrl="/refresh", auto_error=False)


class AuthenticationManager:

    def __init__(
        self,
        key_manager: BaseKeyManager,
        user_manager: BaseUserManager,
        session_manager: SessionManager,
    ) -> None:
        self.keys = key_manager
        self.users = user_manager
        self.sessions = session_manager


    def get_auth_context(
        self,
        api_key: Annotated[str | None, Depends(api_key_header)],
        oauth2_token: Annotated[str | None, Depends(oauth2_scheme)],
    ) -> AuthContext:
        if not (api_key or oauth2_token):
            raise UnauthorizedError("X-API-KEY or Bearer token are required")

        user_records = None
        if api_key:
            key_record = self.keys.read_from_unhashed_key(api_key)
            user_records = self.users.read(email=key_record.user)
        elif oauth2_token:
            if not self.sessions.validate(UUID(oauth2_token)):
                raise UnauthorizedError("session invalid")
            session_record = self.sessions.get(uuid=UUID(oauth2_token))
            user_records = self.users.read(email=session_record.user)

        if not user_records:
            raise UnauthorizedError("user not found")
        
        user = user_records[0]
        email = cast(str, user.email)
        role = cast(str, user.role)

        return AuthContext(
            user_email = email,
            user_role = role, session_id=UUID(oauth2_token))