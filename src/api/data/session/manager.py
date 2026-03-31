from uuid import UUID
from datetime import datetime, timedelta
from typing import cast

from ....exceptions.errors import (
    BadRequestError,
    NotFoundError,
)
from .repository import SQLSessionRepository
from ....utils.models import Session

from ....utils.logger import logger


class SessionManager:

    VALID_FOR_SECONDS = 600
    MAX_VALID_HOURS = 2
    EXTEND_THRESHOLD_SECONDS = 200
    EXTEND_SECONDS = 400
    PURGE_INTERVAL_SECONDS = 180

    def __init__(self, repository: SQLSessionRepository) -> None:
        self.sessions = repository
        self._last_purge_at: datetime | None = None


    def get(self, *, email: str | None = None, uuid: UUID | None = None) -> Session:
        self.cleanup_expired()

        if not (email is not None or uuid is not None):
            raise BadRequestError(f"one of [email, uuid] has to be specified")
        
        if email:
            timestamp = datetime.now() + timedelta(seconds=SessionManager.VALID_FOR_SECONDS)
            session = self.sessions.create(email, datetime.now(), timestamp)
        elif uuid:
            sessions = self.sessions.read(id=uuid)
            if not sessions:
                raise NotFoundError(f"session {uuid} does not exist")
            session = sessions[0]
        else:
            raise BadRequestError(f"email and uuid can not be empty")

        return session
    

    def extend(self, uuid: UUID, created_at: datetime, valid_until: datetime) -> Session | None:
        refresh_threshold = timedelta(seconds = SessionManager.EXTEND_THRESHOLD_SECONDS)
        max_hours = timedelta(hours=SessionManager.MAX_VALID_HOURS)
        
        if (valid_until - datetime.now() < refresh_threshold 
            and datetime.now() - created_at < max_hours):
            
            timestamp = valid_until + timedelta(seconds = SessionManager.EXTEND_SECONDS)
            logger.debug(f"Extending {str(uuid)[:6]} until {timestamp}")

            session = self.sessions.update(uuid, valid_until=timestamp)
            return session
        logger.debug(f"Not extending {str(uuid)[:6]} ({valid_until - datetime.now() < refresh_threshold} and {datetime.now() - created_at < max_hours})")


    def validate(self, uuid: UUID) -> bool:
        self.cleanup_expired()

        sessions = self.sessions.read(id=uuid)
        if not sessions:
            return False
        session = sessions[0]

        timestamp = datetime.now()
        if cast(datetime, session.valid_until) < timestamp:
            return False

        return True


    def cleanup_expired(self, *, force: bool = False) -> int:
        now = datetime.now()
        if not force and self._last_purge_at is not None:
            elapsed = (now - self._last_purge_at).total_seconds()
            if elapsed < SessionManager.PURGE_INTERVAL_SECONDS:
                return 0

        deleted = self.sessions.delete_expired(now)
        self._last_purge_at = now
        if deleted > 0:
            logger.info(f"Purged {deleted} expired sessions")
        return deleted


    def delete(self, uuid: UUID) -> Session:
        deleted = self.sessions.delete(uuid)
        return deleted
