from datetime import datetime
from typing import cast

from ....utils.models import ApiKey
from ..models.api_key import ApiKey as ApiKeyModel


def apikey_from_record(record: ApiKey) -> ApiKeyModel:
    """Maps an API key record to it's pydantic model"""
    revoked_time = None
    if record.revoked_at is not None:
        revoked_time = cast(datetime, record.revoked_at)

    return ApiKeyModel(
        active=cast(bool, record.active),
        name=cast(str, record.name),
        created_at=cast(datetime, record.created_at),
        last_used_at=cast(datetime, record.last_used_at),
        revoked_at=revoked_time,
        user=cast(str, record.user.email),
    )
