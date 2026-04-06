from datetime import datetime, timedelta
from typing import cast
from abc import ABC, abstractmethod
from uuid import UUID

from .repository import BaseSessionRepository, SQLSessionRepository
from ..models.session import Session
from ..mappers.session import session_from_record

from ....utils.logger import logger
from ....exceptions.errors import (
    BadRequestError,
    NotFoundError,
    UnauthorizedError,
)


class BaseSessionManager(ABC):
    """Class serving as a translation layer between the database and the API."""

    VALID_FOR_SECONDS = 600
    MAX_VALID_HOURS = 2
    EXTEND_THRESHOLD_SECONDS = 200
    EXTEND_SECONDS = 400
    PURGE_INTERVAL_SECONDS = 180

    def __init__(self, repository: BaseSessionRepository) -> None:
        self.storage = repository

    @abstractmethod
    def get(self, *, email: str | None = None, uuid: UUID | None = None) -> Session:
        """
        Exactly one of email or uuid has to be provided.
        If email is provided, a new session is created and returned.
        If uuid is provided, an existing session is retrieved and returned.

        Args:
            email: The user's email address who made the request.
            uuid: The session's uuid (access_token).

        Returns:
            Sesssion: The session model.

        Raises:
            BadRequestError: If email and uuid were not provided or are empty.
            NotFoundError: If the session with `uuid` does not exist.
            UnauthorizedError: If the session with `uuid` is expired.
        """

    @abstractmethod
    def extend(self, uuid: UUID) -> Session:
        """
        Increases the valid_until timestamp of a session with `uuid` by `EXTEND_SECONDS` iff
        there is less than `EXTEND_THRESHOLD_SECONDS` left until expiration and the session
        was created at most `MAX_VALID_HOURS` ago.

        Args:
            uuid: The session's uuid.

        Returns:
            Session: New session object with a rotated uuid.

        Raises:
            UnauthorizedError: If the session expired.
            BadRequestError: If the session doesn't exist.
        """

    @abstractmethod
    def validate(self, uuid: UUID) -> bool:
        """
        Checks if a session expired.

        Args:
            uuid: The session's uuid.

        Returns:
            bool: True if the session hasn't expired, False otherwise.
        """

    @abstractmethod
    def delete(self, uuid: UUID) -> Session:
        """
        Deletes a session.

        Args:
            uuid: The session's uuid.
        
        Returns:
            Session: The deleted session model.
        """


class SQLSessionManager(BaseSessionManager):

    def __init__(self, repository: SQLSessionRepository) -> None:
        self.storage = repository
        self._last_purge_at: datetime | None = None


    def get(self, *, email: str | None = None, uuid: UUID | None = None) -> Session:
        self._cleanup_expired()

        if email is None and uuid is None:
            raise BadRequestError(f"one of [email, uuid] has to be specified")
        
        if email:
            timestamp = datetime.now() + timedelta(seconds=SQLSessionManager.VALID_FOR_SECONDS)
            record = self.storage.create(email, datetime.now(), timestamp)
        elif uuid:
            sessions = self.storage.read(id=uuid)
            if not sessions:
                raise NotFoundError(f"session {uuid} does not exist")
            record = sessions[0]
            if cast(datetime, record.valid_until) < datetime.now():
                raise UnauthorizedError(f"session {uuid} expired")
        else:
            raise BadRequestError(f"email and uuid can not be empty")

        return session_from_record(record)
    

    def extend(self, uuid: UUID) -> Session:

        if not self.validate(uuid):
            raise UnauthorizedError("session is not valid")

        old_records = self.storage.read(id=uuid)
        if not old_records:
            raise BadRequestError("session not found")
        old_record = old_records[0]

        created_at = cast(datetime, old_record.valid_until)
        valid_until = cast(datetime, old_record.valid_until)
        user_email = cast(str, old_record.user)
        
        refresh_threshold = timedelta(seconds = SQLSessionManager.EXTEND_THRESHOLD_SECONDS)
        max_hours = timedelta(hours=SQLSessionManager.MAX_VALID_HOURS)
        
        now = datetime.now()

        if (valid_until - now < refresh_threshold and now - created_at < max_hours):

            timestamp = valid_until + timedelta(seconds = SQLSessionManager.EXTEND_SECONDS)

            new_record = self.storage.create(
                user_email=user_email,
                created_at=created_at,
                valid_until=timestamp
            )
            self.storage.delete(uuid)
            logger.debug(f"Extended {str(uuid)[:6]} until {timestamp}. New UUID: {new_record.id}")
            
            return session_from_record(new_record)
        
        logger.debug(f"Not extending {str(uuid)[:6]}")
        return self.get(uuid=uuid)



    def validate(self, uuid: UUID) -> bool:
        self._cleanup_expired()

        sessions = self.storage.read(id=uuid)
        if not sessions:
            return False
        session = sessions[0]

        timestamp = datetime.now()
        if cast(datetime, session.valid_until) < timestamp:
            return False

        return True


    def delete(self, uuid: UUID) -> Session:
        return session_from_record(self.storage.delete(uuid))


    def _cleanup_expired(self, *, force: bool = False) -> int:
        now = datetime.now()
        if not force and self._last_purge_at is not None:
            elapsed = (now - self._last_purge_at).total_seconds()
            if elapsed < SQLSessionManager.PURGE_INTERVAL_SECONDS:
                return 0

        deleted_count = self.storage.delete_expired(now)
        self._last_purge_at = now

        if deleted_count > 0:
            logger.info(f"Purged {deleted_count} expired sessions")
        return deleted_count