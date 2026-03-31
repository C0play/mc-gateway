from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from ..data.models.session import RegisterRequest, RegisterResponse, LoginResponse
from ..services.user import UserService
from ..services.session import SessionService
from .utils import handle_errors


def build_auth_router(user_service: UserService, session_service: SessionService) -> APIRouter:
    router = APIRouter()

    @router.post("/register", response_model=RegisterResponse)
    @handle_errors
    def user_register_public(data: RegisterRequest):
        return user_service.user_register_public(data)

    @router.post("/login", response_model=LoginResponse)
    @handle_errors
    def session_login_public(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
        email = form_data.username
        return session_service.session_login_public(email, form_data.password)

    return router
