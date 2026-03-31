from fastapi import APIRouter, Depends

from ..models.player import FullPlayer
from ..models.response import ListResponse, MessageResponse
from ..services.player import PlayerService
from .utils import handle_errors


def build_player_admin_router(player_service: PlayerService, require_manage_whitelists) -> APIRouter:
    router = APIRouter(
        prefix="/player",
        tags=["admin: whitelists"],
        dependencies=[Depends(require_manage_whitelists)],
    )

    @router.post("/add", response_model=FullPlayer)
    @handle_errors
    def player_add_admin(player: FullPlayer):
        return player_service.player_add(player.username, player.subdomain)

    @router.delete("/remove", response_model=FullPlayer)
    @handle_errors
    def player_remove_admin(player: FullPlayer):
        return player_service.player_remove(player.username, player.subdomain)

    @router.post("/kick/{username}", response_model=MessageResponse)
    @handle_errors
    def player_kick_admin(username: str):
        return player_service.player_kick(username)

    @router.get("/list/", response_model=ListResponse)
    @handle_errors
    def player_list_admin(username: str | None = None, subdomain: str | None = None):
        return player_service.player_list(subdomain, username)

    return router


def build_player_me_router(player_service: PlayerService, require_user_manage_own_containers) -> APIRouter:
    router = APIRouter(
        prefix="/container/{subdomain}/player",
        tags=["user: whitelists"],
        dependencies=[Depends(require_user_manage_own_containers)],
    )

    @router.post("/add/{username}", response_model=FullPlayer)
    @handle_errors
    def player_add_own(subdomain: str, username: str):
        return player_service.player_add(username, subdomain)

    @router.delete("/remove/{username}", response_model=FullPlayer)
    @handle_errors
    def player_remove_own(subdomain: str, username: str):
        return player_service.player_remove(username, subdomain)

    @router.get("/list/", response_model=ListResponse)
    @handle_errors
    def player_list_own(subdomain: str, username: str | None = None):
        return player_service.player_list(subdomain, username)

    @router.post("/kick/{username}", response_model=MessageResponse)
    @handle_errors
    def player_kick_own(subdomain: str, username: str):
        return player_service.player_kick(username, subdomain)

    return router
