from ....utils.models import Whitelist
from ..models.whitelist import WhitelistEntry


def full_whitelist_from_record(record: Whitelist) -> WhitelistEntry:
    """Maps a whitelist entry record to it's pydantic model"""
    return WhitelistEntry(
        username=str(record.username), subdomain=str(record.container.subdomain)
    )
