from typing import Annotated
from fastapi import APIRouter, Security

from ..security import AuthContext, AuthorizationManager, Permission
from ..data.models.user import User
from ..data.user.repository import BaseUserRepository



class UserRouter:
    """Defines API endpoints used for user management."""

    def __init__(self, user_manager: BaseUserRepository, auth: AuthorizationManager) -> None:
        self.users = user_manager
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/user", tags=["users"])

        REQ = self.auth.require

        @router.get("/", response_model=list[User])
        def fetch_user(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.user_read])],
            email: str | None = None
        ):
            if auth.user_role.requires_ownership:
                return self.users.read(email=auth.user_email)

            return self.users.read(email=email)
        

        @router.put(
            "/update/role", 
            dependencies=[Security(REQ, scopes=[Permission.user_update])],
            response_model=User
        )
        def update_user_role(role: str, email: str):
            return self.users.update(email, role=role)
        

        @router.delete(
            "/delete/{email}",
            dependencies=[Security(REQ, scopes=[Permission.user_delete])],
            response_model=User
        )
        def delete_user(email : str):
            return self.users.delete(email)
        

        return router