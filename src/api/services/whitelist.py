from ..data.mappers.whitelist import full_whitelist_from_record
from ..data.models.whitelist import WhitelistEntry
from ..data.models.response import MessageResponse
from ...exceptions.errors import NotFoundError, ForbiddenError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ...gateway.server import Server



class WhitelistService:
    """Utility class for executing API requests"""

    def __init__(self, server: 'Server') -> None:
        self.whitelist = server._whitelist
        self.server_sessions = server._sessions
        self.containers = server._sessions.containers

    
    def add(self, username: str, subdomain: str) -> WhitelistEntry:
        record = self.whitelist.storage.create(username, subdomain)
        return full_whitelist_from_record(record)

    
    def remove(self, username: str, subdomain: str) -> WhitelistEntry:
        records = self.whitelist.storage.read(subdomain=subdomain)
        if not records:
            raise NotFoundError(f"player {username} is not whitelisted on {subdomain}")
        deleted_record = records[0]

        self.server_sessions.interrupt(
            reason="You were removed from the whitelist",
            username=username,
        )
        self.whitelist.storage.delete(username, subdomain)
        return full_whitelist_from_record(deleted_record)

    
    def read(
        self,
        subdomain: str | None = None,
        username: str | None = None,
        email: str | None = None,
    ) -> list[WhitelistEntry]:

        if email is not None:
            records = self.containers.storage.read(allow_empty=True, owner=email)
            subdomains = [str(r.subdomain) for r in records]
        else:
            subdomains = [subdomain]
        
        lst = []
        for owned_sub in subdomains:
            query = self.whitelist.storage.read(
                username=username,
                container=owned_sub,
            )
            lst += [full_whitelist_from_record(row) for row in query]

        return lst


    def assert_owner(self, subdomain: str, email: str) -> None:
        self.containers.storage.read(
            allow_empty=False,
            subdomain=subdomain,
            owner=email,
        )