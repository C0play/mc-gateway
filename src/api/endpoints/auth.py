from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from ..security import AuthContext, AuthenticationManager
from ..data.models.session import RegisterRequest, RegisterResponse, LoginResponse
from ..data.models.response import MessageResponse
from ..services import UserService, SessionService
from .utils import handle_errors


class AuthRouter:

    def __init__(
        self,
        user_service: UserService,
        session_service: SessionService,
        auth_manager: AuthenticationManager
    ) -> None:
        self.users = user_service
        self.sessions = session_service
        self.auth = auth_manager


    def get_router(self) -> APIRouter:
        
        router = APIRouter()

        @router.post("/register", response_model=RegisterResponse)
        @handle_errors
        def register_user(data: RegisterRequest):
            return self.users.user_register_public(data)


        @router.post("/login", response_model=LoginResponse)
        @handle_errors
        def session_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
            email = form_data.username
            return self.sessions.session_login(email, form_data.password)


        @router.post("/logout", response_model=MessageResponse)
        @handle_errors
        def session_logout(auth: Annotated[AuthContext, Depends(self.auth.get_auth_context)]):
            return self.sessions.session_logout(auth.session_id)


        @router.get("/session", response_model=SessionResponse)
        @handle_errors
        def session_get_own(auth: Annotated[AuthContext, Depends(self.auth.get_auth_context)]):
            return self.sessions.session_get(auth.user_email)



        # @router.


        return router
