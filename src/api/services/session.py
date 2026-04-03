from uuid import UUID
from typing import TYPE_CHECKING

from ..data.models.response import MessageResponse
from ..data.models.session import SessionResponse, RegisterRequest, RegisterResponse
from ..data.mappers.session import session_response_from_record
from ...exceptions.errors import UnauthorizedError, ConflictError

if TYPE_CHECKING:
    from ..data.user.manager import SQLUserManager
    from ..data.session.manager import SessionManager



class SessionService:

    def __init__(self, *, users: 'SQLUserManager', sessions: 'SessionManager') -> None:
        self.users = users
        self.sessions = sessions

    
    def register(self, data: RegisterRequest) -> RegisterResponse:
        try:
            self.users.create(data.email, data.password, "user")
        except ConflictError:
            return RegisterResponse(
                status=False,
                message="User already exists",
            )

        return RegisterResponse(
            status=True,
            message="User registered successfully",
        )
    

    def login(self, email: str, password: str) -> SessionResponse:
        if not self.users.validate_password(email, password):
            raise UnauthorizedError("Wrong password or email")

        session_record = self.sessions.get(email=email)
        return session_response_from_record(session_record, "bearer")

    
    def read(self, uuid: UUID) -> SessionResponse:
        session_record = self.sessions.get(uuid=uuid)
        return session_response_from_record(session_record, "bearer")

    
    def logout(self, uuid: UUID) -> MessageResponse:
        self.sessions.delete(uuid)
        return MessageResponse(message="Session revoked")
    

    def refresh(self, uuid: UUID) -> SessionResponse:
        new_sesion = self.sessions.extend(uuid)
        if not new_sesion:
            new_sesion = self.sessions.get(uuid=uuid)
        
        return session_response_from_record(new_sesion, "bearer")