from typing import Annotated

from fastapi import APIRouter, Depends

from ..data.models.player import FullPlayer
from ..data.models.response import ListResponse, MessageResponse
from ..security import AuthContext, AuthorizationManager, Permission
from ..services.player import PlayerService
from ...exceptions import ForbiddenError
from .utils import handle_errors



class PlayerRouter:

    def __init__(self, player_service: PlayerService, auth: AuthorizationManager) -> None:
        self.players = player_service
        self.auth = auth


    def get_router(self) -> APIRouter:
        
        MANAGE_ANY = self.auth.require_any(
            Permission.whitelist_manage_all,
            Permission.whitelist_manage_own
        )

        router = APIRouter(prefix="/player", tags=["whitelists"])

        @router.post("/add", response_model=FullPlayer)
        @handle_errors
        def create_player(auth: Annotated[AuthContext, Depends(MANAGE_ANY)], player: FullPlayer):
            if not self._is_admin(auth):
                self.players.assert_owner(player.subdomain, auth.user_email)

            return self.players.add(player.username, player.subdomain)


        @router.delete("/remove", response_model=FullPlayer)
        @handle_errors
        def remove_player(auth: Annotated[AuthContext, Depends(MANAGE_ANY)], player: FullPlayer):
            if not self._is_admin(auth):
                self.players.assert_owner(player.subdomain, auth.user_email)

            return self.players.remove(player.username, player.subdomain)


        @router.post("/kick", response_model=MessageResponse)
        @handle_errors
        def kick_player_from_container(auth: Annotated[AuthContext, Depends(MANAGE_ANY)], player: FullPlayer):
            if not self._is_admin(auth):
                self.players.assert_owner(player.subdomain, auth.user_email)
            
            return self.players.kick(player.username, player.subdomain)


        @router.get("/list/", response_model=ListResponse)
        @handle_errors
        def fetch_player(
            auth: Annotated[AuthContext, Depends(MANAGE_ANY)], 
            username: str | None = None,
            subdomain: str | None = None
        ):
            if not self._is_admin(auth):
                if subdomain is None:
                    raise ForbiddenError("a subdomain has to be provided")
                self.players.assert_owner(subdomain, auth.user_email)
                
            return self.players.read(subdomain, username)


        return router
    

    # =================================== HELPERS ===================================

    def _is_admin(self, auth_context: AuthContext) -> bool:
        return self.auth.roles.validate(Permission.whitelist_manage_all, auth_context.user_role)