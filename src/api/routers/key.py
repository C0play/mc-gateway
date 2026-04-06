from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Security

from ..data.api_key.repository import BaseKeyRepository
from ..data.models.response import MessageResponse
from ..data.models.api_key import ApiKey
from ..security import AuthContext, AuthorizationManager, Permission



class ApiKeyRouter:
    """Defines API endpoints used for api key management."""

    def __init__(self, api_key_manager: BaseKeyRepository, auth: AuthorizationManager) -> None:  
        self.api_keys = api_key_manager
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/apikey", tags=["api keys"])

        REQ = self.auth.require

        @router.post("/create", response_model=MessageResponse)
        def create_api_key(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.api_key_create])],
            email: str | None,
            name: str | None
        ):
            if name is None:
                name = "default" + str(datetime.now().microsecond)[:4]

            if auth.user_role.requires_ownership:
                return self.api_keys.create(auth.user_email, name)
            
            if email is not None:
                return self.api_keys.create(email, name)
            else:
                return self.api_keys.create(auth.user_email, name)


        @router.get("/list", response_model=list[ApiKey])
        def fetch_api_keys(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.api_key_read])],
            name: str | None = None,
            email: str | None = None
        ):
            if auth.user_role.requires_ownership:
                return self.api_keys.read(
                    user = auth.user_email,
                    name = name
                )
            
            return self.api_keys.read(user=email, name=name)
        

        @router.delete("/revoke/{name}", response_model=MessageResponse)
        def revoke_api_key(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.api_key_revoke])],
            name: str,
            email: str | None,
        ):
            if auth.user_role.requires_ownership:
                return self.api_keys.update(auth.user_email, name, active=False)
            
            if email is not None:
                return self.api_keys.update(email, name, active=False)
            else:
                return self.api_keys.update(auth.user_email, name, active=False)
        
        
        @router.delete(
            "/delete/{name}",
            dependencies=[Security(REQ, scopes=[Permission.api_key_delete])],
            response_model=MessageResponse
        )
        def delete_api_key(name: str, owner_email: str):
            return self.api_keys.delete(owner_email, name)


        return router