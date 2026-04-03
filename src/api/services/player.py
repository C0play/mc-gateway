from ..data.mappers.whitelist import full_whitelist_from_record
from ..data.models.player import FullPlayer
from ..data.models.response import ListResponse, MessageResponse
from ...exceptions.errors import NotFoundError, ForbiddenError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ...gateway.server import Server



class PlayerService:

    def __init__(self, *, server: 'Server') -> None:
        self.whitelist = server._whitelist
        self.server_sessions = server._sessions

    
    def add(self, username: str, subdomain: str) -> FullPlayer:
        new_player = self.whitelist.storage.create(username, subdomain)
        return full_whitelist_from_record(new_player)

    
    def remove(self, username: str, subdomain: str) -> FullPlayer:
        records = self.whitelist.storage.read(subdomain=subdomain)
        if not records:
            raise NotFoundError(f"player {username} is not whitelisted on {subdomain}")
        deleted_player = records[0]

        self.server_sessions.interrupt(
            reason="You were removed from the whitelist",
            username=username,
        )
        self.whitelist.storage.delete(username, subdomain)
        return full_whitelist_from_record(deleted_player)

    
    def read(self, subdomain: str | None = None, username: str | None = None) -> ListResponse:
        query = self.whitelist.storage.read(
            username=username,
            container=subdomain,
        )
        lst = [full_whitelist_from_record(row) for row in query]
        return ListResponse(root=lst)


    def kick(self, username: str, subdomain: str) -> MessageResponse:
        if subdomain is not None:
            records = self.whitelist.storage.read(username=username, container=subdomain)
            if not records:
                raise NotFoundError(f"player {username} is not whitelisted on {subdomain}")

            self.server_sessions.interrupt(username=username)
            return MessageResponse(
                message=f"Player {username} has been kicked from server {subdomain}"
            )

        self.server_sessions.interrupt(username=username)
        return MessageResponse(message=f"Player {username} has been kicked")
    

    def assert_owner(self, subdomain: str, owner_email: str) -> None:
        records = self.server_sessions.containers.storage.read(
            subdomain=subdomain,
            owner=owner_email,
        )
        if not records:
            raise ForbiddenError("you are no the owner")