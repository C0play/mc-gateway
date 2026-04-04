from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends

from ..data.api_key.manager import SQLKeyManager
from ..data.models.response import ListResponse, MessageResponse
from ..security import AuthContext, AuthorizationManager, Permission
from .utils import handle_errors



class ApiKeyRouter:

    def __init__(self, api_key_manager: SQLKeyManager, auth: AuthorizationManager) -> None:  
        self.api_keys = api_key_manager
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/apikey", tags=["api keys"])

        MANAGE_ALL = self.auth.require_any(
            Permission.api_keys_manage_all
        )
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


        @router.get("/list", response_model=ListResponse)
        @handle_errors
        def fetch_api_keys(
            auth: Annotated[AuthContext, Depends(MANAGE_ANY)],
            name: str | None = None,
            email: str | None = None
        ):
            if not self._is_admin(auth):
                return self.api_keys.read(
                    user = auth.user_email,
                    name = name
                )
            
            return self.api_keys.read(user=email, name=name)
        

        @router.delete("/revoke/{name}", response_model=MessageResponse)
        @handle_errors
        def revoke_api_key(
            auth: Annotated[AuthContext, Depends(MANAGE_ANY)],
            name: str,
            owner_email: str | None,
        ):
            if not self._is_admin(auth):
                return self.api_keys.deactivate(auth.user_email, name)
            
            if owner_email is not None:
                return self.api_keys.deactivate(owner_email, name)
            else:
                return self.api_keys.deactivate(auth.user_email, name)
        
        
        @router.delete(
            "/delete/{name}",
            dependencies=[Depends(MANAGE_ALL)],
            response_model=MessageResponse
        )
        @handle_errors
        def delete_api_key(name: str, owner_email: str):
            return self.api_keys.delete(owner_email, name)


        return router
    
    
    # =================================== HELPERS ===================================

    def _is_admin(self, auth_context: AuthContext) -> bool:
        return self.auth.roles.validate(Permission.api_keys_manage_all, auth_context.user_role)
