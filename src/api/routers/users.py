from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from ..security import AuthContext, AuthorizationManager, Permission
from ..data.models.response import ListResponse, MessageResponse
from ..data.models.user import User
from ..data.user.manager import BaseUserManager
from .utils import handle_errors



class UserRouter:

    def __init__(self, user_manager: BaseUserManager, auth: AuthorizationManager) -> None:
        self.users = user_manager
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(
            prefix="/user",
            tags=["users"]
        )

        MANAGE_ALL = self.auth.require(
            Permission.users_manage_all
        )
        MANAGE_OWN = self.auth.require(
            Permission.users_manage_own
        )
        MANAGE_ANY = self.auth.require_any(
            Permission.users_manage_all,
            Permission.users_manage_own
        )


        @router.get("/", response_model=list[User])
        @handle_errors
        def fetch_user(
            auth: Annotated[AuthContext, Depends(MANAGE_ANY)],
            email: str | None = None
        ):
            if self._is_admin(auth):
                return self.users.read(email=email)
            
            if email is not None and auth.user_email != email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="you are not authorized to view accounts beside your own"
                )
            return self.users.read(email=auth.user_email)
        

        @router.put("/update/role", response_model=User)
        @handle_errors
        def update_user_role(
            auth: Annotated[AuthContext, Depends(MANAGE_ALL)],
            role: str,
            email: str | None = None
        ):
            if email is not None:
                return self.users.update(email, role=role)
            
            return self.users.update(auth.user_email, role=role)
        

        @router.delete("/delete/", response_model=User)
        @handle_errors
        def delete_user(
            auth: Annotated[AuthContext, Depends(MANAGE_ALL)],
            email : str
        ):
            return self.users.delete(email)
        

        return router


    # =================================== HELPERS ===================================

    def _is_admin(self, auth_context: AuthContext) -> bool:
        return self.auth.roles.validate(Permission.users_manage_all, auth_context.user_role)