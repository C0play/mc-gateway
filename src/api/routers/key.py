from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends

from ..data.models.response import ListResponse, MessageResponse
from ..security import AuthContext, AuthorizationManager, Permission
from ..services.key import ApiKeyService
from .utils import handle_errors



class ApiKeyRouter:

    def __init__(self, api_key_service: ApiKeyService, auth: AuthorizationManager) -> None:  
        self.auth = auth
        self.api_keys = api_key_service


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/apikey", tags=["api keys"])

        MANAGE_ANY = self.auth.require_any(
            Permission.api_keys_manage_own,
            Permission.api_keys_manage_all
        )

        @router.post("/create", response_model=MessageResponse)
        @handle_errors
        def create_api_key(
            auth: Annotated[AuthContext, Depends(MANAGE_ANY)],
            owner_email: str | None,
            name: str | None
        ):
            if name is None:
                name = "default" + str(datetime.now().microsecond)[:4]

            if not self._is_admin(auth):
                return self.api_keys.create(auth.user_email, name)
            
            if owner_email is not None:
                return self.api_keys.create(owner_email, name)
            else:
                return self.api_keys.create(auth.user_email, name)


        @router.get("/apikey/list", response_model=ListResponse)
        @handle_errors
        def fetch_api_keys(
            auth: Annotated[AuthContext, Depends(MANAGE_ANY)],
            name: str | None = None,
            email: str | None = None
        ):
            if not self._is_admin(auth):
                return self.api_keys.read(auth.user_email, name)
            
            return self.api_keys.read(email=email, name=name)
        

        @router.delete("/revoke/{name}", response_model=MessageResponse)
        @handle_errors
        def revoke_api_key(
            auth: Annotated[AuthContext, Depends(MANAGE_ANY)],
            name: str,
            owner_email: str | None,
        ):
            if not self._is_admin(auth):
                return self.api_keys.revoke(auth.user_email, name)
            
            if owner_email is not None:
                return self.api_keys.revoke(owner_email, name)
            else:
                return self.api_keys.revoke(auth.user_email, name)


        return router
    
    # =================================== HELPERS ===================================

    def _is_admin(self, auth_context: AuthContext) -> bool:
        return self.auth.roles.validate(Permission.api_keys_manage_all, auth_context.user_role)
