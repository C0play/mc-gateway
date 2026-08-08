from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Security
from pydantic import EmailStr

from ..data.api_key.repository import BaseKeyRepository
from ..data.models.api_key import ApiKey
from ..security import AuthContext, AuthorizationManager, Permission
from ...exceptions import ForbiddenError


class ApiKeyRouter:
    """Defines API endpoints used for api key management."""

    def __init__(self, api_key_manager: BaseKeyRepository, auth: AuthorizationManager) -> None:  
        self.api_keys = api_key_manager
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/api-keys", tags=["api keys"])

        REQ = self.auth.require

        @router.post("/", response_model=str)
        def create_api_key(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.api_key_create])],
            email: EmailStr,
            name: str,
        ):
            if auth.user_role.requires_ownership and auth.user_email != email:
                raise ForbiddenError("You can only modify your own keys.")
            
            return self.api_keys.create(email, name)


        @router.get("/", response_model=list[ApiKey])
        def fetch_api_keys(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.api_key_read])],
            email: EmailStr | None = None,
            name: str | None = None,
        ):
            if auth.user_role.requires_ownership:
                if email is not None and auth.user_email != email:
                    raise ForbiddenError("You can only view your own keys.")
                return self.api_keys.read(
                    user = auth.user_email,
                    name = name
                )
            
            return self.api_keys.read(user=email, name=name)
        

        @router.delete("/revoke", response_model=ApiKey)
        def revoke_api_key(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.api_key_revoke])],
            email: EmailStr,
            name: str,
        ):
            if auth.user_role.requires_ownership and auth.user_email != email:
                raise ForbiddenError("You can only modify your own keys.")

            now = datetime.now()
            return self.api_keys.update(email, name, active=False, revoked_at=now)
        
        
        @router.delete(
            "/remove",
            dependencies=[Security(REQ, scopes=[Permission.api_key_delete])],
            response_model=ApiKey
        )
        def delete_api_key(email: EmailStr, name: str):
            return self.api_keys.delete(email, name)


        return router