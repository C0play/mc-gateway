from typing import Annotated

from fastapi import APIRouter, Depends

from ..data.models.response import ListResponse, MessageResponse
from ..security import AuthContext, AuthorizationManager, Permission
from ..services.api_key import ApiKeyService
from ..services.session import SessionService
from .utils import handle_errors


class ApiKeyRouter:

    def __init__(self, api_key_service: ApiKeyService, auth: AuthorizationManager) -> None:  
        self.auth = auth
        self.api_keys = api_key_service

    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/apikey")

        MANAGE_ALL = self.auth.require(Permission.api_keys_manage_all)
        MANAGE_ANY = self.auth.require_any(
            Permission.api_keys_manage_own,
            Permission.api_keys_manage_all
        )

        @router.get("/apikey/list", response_model=ListResponse)
        @handle_errors
        def get_api_keys(auth: Annotated[AuthContext, Depends(MANAGE_ANY)], name: str | None = None):
            if not self._is_admin(auth):
                self.api_keys.validate_owner(owner_email=auth.user_email)    
                return self.api_keys.read(auth.user_email, name)
            
            return self.api_keys.read(name=name)


        @router.post("/create", response_model=MessageResponse)
        @handle_errors
        def create_api_key(auth: Annotated[AuthContext, Depends(MANAGE_ANY)]):
            if self._is_admin(auth):

            return self.api_keys.create(auth.email)


        @router.delete("/revoke/{name}", response_model=MessageResponse)
        @handle_errors
        def revoke_api_key(auth: Annotated[AuthContext, Depends(MANAGE_ANY)], name: str):
            return self.api_keys.revoke(auth.email, name)


        return router
    
    def _is_admin(self, auth_context: AuthContext) -> bool:
        return self.auth.roles.validate(Permission.api_keys_manage_all, auth_context.user_role)
