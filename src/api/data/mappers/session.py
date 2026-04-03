from typing import cast
from datetime import datetime

from ....utils.models import Session as SessionRecord
from ..models.session import Session, SessionResponse


def session_from_record(record: SessionRecord) -> Session:
    return Session(
        user_email=str(record.user),
        access_token=str(record.id),
        created_at=cast(datetime, record.created_at),
        valid_until=cast(datetime, record.valid_until),
    )


def session_response_from_record(record: SessionRecord, token_type: str) -> SessionResponse:
    session = session_from_record(record)
    return SessionResponse(
        **session.model_dump(),
        token_type=token_type,
    )