from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from ..security import AuthContext, AuthenticationManager
from ..data.models.session import RegisterRequest, RegisterResponse, SessionResponse
from ..data.models.response import MessageResponse
from ..services import SessionService
from .utils import handle_errors
from ...exceptions import BadRequestError



class AuthRouter:

    def __init__(
        self,
        session_service: SessionService,
        auth_manager: AuthenticationManager
    ) -> None:
        self.sessions = session_service
        self.auth = auth_manager


    def get_router(self) -> APIRouter:
        
        router = APIRouter(tags=["authentication"])

        @router.post("/register", response_model = RegisterResponse)
        @handle_errors
        def register_user(data: RegisterRequest):
            return self.sessions.register(data)


        @router.post("/login", response_model = SessionResponse)
        @handle_errors
        def session_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
            email = form_data.username
            return self.sessions.login(email, form_data.password)


        @router.post("/logout", response_model = MessageResponse)
        @handle_errors
        def session_logout(auth: Annotated[AuthContext, Depends(self.auth.require_bearer)]):
            if not auth.session_id:
                raise BadRequestError(f"this action requires bearer authentication")
            return self.sessions.logout(auth.session_id)


        @router.get("/session", response_model = SessionResponse)
        @handle_errors
        def session_get(auth: Annotated[AuthContext, Depends(self.auth.require_bearer)]):
            if not auth.session_id:
                raise BadRequestError(f"this action requires bearer authentication")
            return self.sessions.read(auth.session_id)


        @router.post("/refresh", response_model = SessionResponse)
        @handle_errors
        def session_refresh(auth: Annotated[AuthContext, Depends(self.auth.require_bearer)]):
            if not auth.session_id:
                raise BadRequestError(f"this action requires bearer authentication")
            return self.sessions.refresh(auth.session_id)


        return router
