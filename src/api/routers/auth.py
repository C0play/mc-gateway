from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from ..security import AuthContext, AuthenticationManager
from ..data.session.manager import BaseSessionManager
from ..data.user.repository import BaseUserRepository
from ..data.models.session import RegisterRequest, RegisterResponse, SessionResponse
from ..data.models.response import MessageResponse
from ...exceptions import BadRequestError, ConflictError, UnauthorizedError



class AuthRouter:
    """Defines API endpoints used for authentication like login, logout, register."""

    def __init__(
        self,
        sessions: BaseSessionManager,
        users: BaseUserRepository,
        auth_manager: AuthenticationManager
    ) -> None:
        self.sessions = sessions
        self.users = users
        self.auth = auth_manager


    def get_router(self) -> APIRouter:
        
        router = APIRouter(prefix="/auth", tags=["authentication"])

        @router.post("/register", response_model = RegisterResponse)
        def register_user(data: RegisterRequest):
            try:
                self.users.create(data.email, data.password, "user")
            except ConflictError:
                return RegisterResponse(
                    status=False,
                    message="User with that email already exists."
                )
            return RegisterResponse(
                status=True,
                message="Registration was successfull."
            )


        @router.post("/login", response_model = SessionResponse)
        def session_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
            if not self.users.validate_password(form_data.username, form_data.password):
                raise UnauthorizedError("Wrong password or email")

            return self.sessions.get(email=form_data.username)


        @router.post("/logout", response_model = MessageResponse)
        def session_logout(auth: Annotated[AuthContext, Depends(self.auth.require_bearer)]):
            if not auth.session_id:
                raise BadRequestError(f"this action requires bearer authentication")
            
            self.sessions.delete(auth.session_id)
            return MessageResponse(message="Session revoked")


        @router.get("/session", response_model = SessionResponse)
        def session_get(auth: Annotated[AuthContext, Depends(self.auth.require_bearer)]):
            if not auth.session_id:
                raise BadRequestError(f"this action requires bearer authentication")
            return self.sessions.get(uuid=auth.session_id)


        @router.post("/refresh", response_model = SessionResponse)
        def session_refresh(auth: Annotated[AuthContext, Depends(self.auth.require_bearer)]):
            if not auth.session_id:
                raise BadRequestError(f"this action requires bearer authentication")
            return self.sessions.extend(auth.session_id)


        return router
