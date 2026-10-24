from datetime import datetime
from typing import cast

from ....utils.models import Session
from ..models.session import Session as SessionModel


def session_from_record(record: Session) -> SessionModel:
    """Maps a session record to it's pydantic model."""
    return SessionModel(
        user_email=str(record.user),
        access_token=str(record.id),
        created_at=cast(datetime, record.created_at),
        valid_until=cast(datetime, record.valid_until),
    )
