from typing import cast
from datetime import datetime

from ....utils.models import SessionRecord as SessionRecord
from ..models.session import Session


def session_from_record(record: SessionRecord) -> Session:
    """Maps a session record to it's pydantic model."""
    return Session(
        user_email      = str(record.user),
        access_token    = str(record.id),
        created_at      = cast(datetime, record.created_at),
        valid_until     = cast(datetime, record.valid_until),
    )