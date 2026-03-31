from ..models.player import FullPlayer
from ....utils.models import Whitelist as WhitelistRecord


def full_whitelist_from_record(record: WhitelistRecord) -> FullPlayer:
    return FullPlayer(
        username        = str(record.username),
        subdomain       = str(record.container.subdomain)
    )