from typing import Annotated
from fastapi import APIRouter, Security

from ..data.models.whitelist import WhitelistEntry
from ..data.models.response import MessageResponse
from ..security import AuthContext, AuthorizationManager, Permission
from ..services.whitelist import WhitelistService


class WhitelistRouter:
    """Defines API endpoints used for whitelist management."""

    def __init__(self, whitelist_service: WhitelistService, auth: AuthorizationManager) -> None:
        self.whitelists = whitelist_service
        self.auth = auth


    def get_router(self) -> APIRouter:
        
        router = APIRouter(prefix="/whitelists", tags=["whitelists"])

        REQ = self.auth.require

        @router.post("/", response_model=WhitelistEntry)
        def create_whitelist_entry(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.whitelist_create])],
            username: str,
            subdomain: str,
        ):
            if auth.user_role.requires_ownership:
                self.whitelists.assert_owner(subdomain, auth.user_email)

            return self.whitelists.add(username, subdomain)


        @router.get("/", response_model=list[WhitelistEntry])
        def fetch_whitelist_entry(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.whitelist_read])], 
            username: str | None = None,
            subdomain: str | None = None
        ):
            if auth.user_role.requires_ownership:
                return self.whitelists.read(subdomain, username, auth.user_email)
                
            return self.whitelists.read(subdomain, username)


        @router.delete("/", response_model=WhitelistEntry)
        def remove_whitelist_entry(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.whitelist_delete])],
            username: str,
            subdomain: str,
        ):
            if auth.user_role.requires_ownership:
                self.whitelists.assert_owner(subdomain, auth.user_email)

            return self.whitelists.remove(username, subdomain)


        @router.post("/{subdomain}/kick", response_model=MessageResponse)
        def kick_player_from_container(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.whitelist_kick])],
            username: str,
            subdomain: str,
        ):
            if auth.user_role.requires_ownership:
                self.whitelists.assert_owner(subdomain, auth.user_email)
            
            return self.whitelists.kick(username, subdomain)


        return router