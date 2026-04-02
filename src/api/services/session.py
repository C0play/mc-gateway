from uuid import UUID

from ..data.models.response import MessageResponse
from ..data.models.session import LoginResponse
from ...exceptions.errors import UnauthorizedError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..data.user.manager import SQLUserManager
    from ..data.session.manager import SessionManager


class SessionService:

    def __init__(self, *, users: 'SQLUserManager', sessions: 'SessionManager') -> None:
        self.users = users
        self.sessions = sessions

    
    def session_login(self, email: str, password: str) -> LoginResponse:
        if not self.users.validate_password(email, password):
            raise UnauthorizedError("Wrong password or email")

        session = self.sessions.get(email=email)
        return LoginResponse(
            access_token=str(session.id),
            token_type="bearer",
        )

    
    def session_get(self, email: str) -> MessageResponse:
        return MessageResponse(message=f"Session valid for {email}")

    
    def session_logout(self, session_id: UUID) -> MessageResponse:
        self.sessions.delete(session_id)
        return MessageResponse(message="Session revoked")