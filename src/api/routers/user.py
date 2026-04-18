from typing import Annotated
from fastapi import APIRouter, Security

from ..security import AuthContext, AuthorizationManager, Permission
from ..data.models.user import User
from ..data.user.repository import BaseUserRepository
from ..security.roles import RoleRepository



class UserRouter:
    """Defines API endpoints used for user management."""

    def __init__(
        self,
        role_repo: RoleRepository,
        user_manager: BaseUserRepository,
        auth: AuthorizationManager
    ) -> None:
        self.roles = role_repo
        self.users = user_manager
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/users", tags=["users"])

        REQ = self.auth.require

        @router.get("/", response_model=list[User])
        def fetch_user(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.user_read])],
            email: str | None = None
        ):
            if auth.user_role.requires_ownership:
                return self.users.read(email=auth.user_email)

            return self.users.read(email=email)
        

        @router.get(
            "/roles",
            dependencies=[Security(REQ, scopes=[Permission.user_read])],
            response_model=list[str]
        )
        def fetch_roles():
            return [r.name for r in self.roles.get_all()]


        @router.put(
            "/{email}/role",
            dependencies=[Security(REQ, scopes=[Permission.user_view_roles])],
            response_model=User
        )
        def update_user_role(email: str, role: str):
            self.roles.get(role) # will raise if role does not exist
            return self.users.update(email, role=role)
        

        @router.delete(
            "/{email}",
            dependencies=[Security(REQ, scopes=[Permission.user_delete])],
            response_model=User
        )
        def delete_user(email : str):
            return self.users.delete(email)
        

        return router