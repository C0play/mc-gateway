from ..models.whitelist import WhitelistEntry
from ....utils.models import Whitelist as WhitelistRecord


def full_whitelist_from_record(record: WhitelistRecord) -> WhitelistEntry:
    """Maps a whitelist entry record to it's pydantic model"""
    return WhitelistEntry(
        username        = str(record.username),
        subdomain       = str(record.container.subdomain)
    )