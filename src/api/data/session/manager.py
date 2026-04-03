from uuid import UUID
from datetime import datetime, timedelta
from typing import cast

from ....exceptions.errors import (
    BadRequestError,
    NotFoundError,
    UnauthorizedError,
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
        self._cleanup_expired()

        if email is None and uuid is None:
            raise BadRequestError(f"one of [email, uuid] has to be specified")
        
        if email:
            timestamp = datetime.now() + timedelta(seconds=SessionManager.VALID_FOR_SECONDS)
            session = self.sessions.create(email, datetime.now(), timestamp)
        elif uuid:
            sessions = self.sessions.read(id=uuid)
            if not sessions:
                raise NotFoundError(f"session {uuid} does not exist")
            session = sessions[0]
            if cast(datetime, session.valid_until) < datetime.now():
                raise UnauthorizedError(f"session {uuid} expired")
        else:
            raise BadRequestError(f"email and uuid can not be empty")

        return session
    

    def extend(self, uuid: UUID) -> Session | None:

        if not self.validate(uuid):
            raise UnauthorizedError("session is not valid")

        old_sessions = self.sessions.read(id=uuid)
        if not old_sessions:
            raise BadRequestError("session not found")
        old_session = old_sessions[0]

        created_at = cast(datetime, old_session.valid_until)
        valid_until = cast(datetime, old_session.valid_until)
        user_email = cast(str, old_session.user)
        
        refresh_threshold = timedelta(seconds = SessionManager.EXTEND_THRESHOLD_SECONDS)
        max_hours = timedelta(hours=SessionManager.MAX_VALID_HOURS)
        
        now = datetime.now()

        if (valid_until - now < refresh_threshold and now - created_at < max_hours):

            timestamp = valid_until + timedelta(seconds = SessionManager.EXTEND_SECONDS)
            logger.debug(f"Extending {str(uuid)[:6]} until {timestamp}")

            new_session = self.sessions.create(
                user_email=user_email,
                created_at=created_at,
                valid_until=timestamp
            )
            self.sessions.delete(uuid)
            logger.debug(f"Extended {str(uuid)[:6]}. New UUID: {new_session.id}")
            
            return new_session


        logger.debug(f"Not extending {str(uuid)[:6]} ({valid_until - now < refresh_threshold} and {now - created_at < max_hours})")


    def validate(self, uuid: UUID) -> bool:
        self._cleanup_expired()

        sessions = self.sessions.read(id=uuid)
        if not sessions:
            return False
        session = sessions[0]

        timestamp = datetime.now()
        if cast(datetime, session.valid_until) < timestamp:
            return False

        return True


    def _cleanup_expired(self, *, force: bool = False) -> int:
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
