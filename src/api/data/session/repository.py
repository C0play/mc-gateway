import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from peewee import IntegrityError

from ....utils.models import SessionRecord
from ....exceptions.errors import NotFoundError, ConflictError, ServiceError



class BaseSessionRepository(ABC):
    """A base class for managing session parameters stored in persistent storage"""
    
    @abstractmethod
    def create(self, user_email: str, created_at: datetime, valid_until: datetime) -> SessionRecord:
        """
        Creates a new Session.

        Args:
            user_email: The users's email address.
            created_at: Timestamp when the session was created,
            valid_until: Timestamp when the session should become invalid.

        Returns:
            session: Session model instance.

        Raises:
            ConflictError: If a session for the specified email address already exists.
        """
        ...
    
    @abstractmethod
    def read(self, **filters) -> list[SessionRecord]:
        """
        Retrieves Session records matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[Session]: Matching Session model instances.
        """
        ...
    
    @abstractmethod
    def update(self, uuid: uuid.UUID, **fields) -> SessionRecord:
        """
        Updates arbitrary fields on a Session record.

        Args:
            uuid: The session UUID.
            **fields: Field names and their new values.

        Returns:
            Session: The updated Session instance.

        Raises:
            NotFoundError: If the session does not exist.
        """
        ...

    @abstractmethod
    def delete(self, uuid: uuid.UUID) -> SessionRecord:
        """
        Removes a Session record.

        Args:
            uuid: The session UUID.

        Raises:
            NotFoundError: If the Session does not exist.
        """
        ...

    @abstractmethod
    def delete_expired(self, now: datetime) -> int:
        """
        Removes all sessions where valid_until is older than now.

        Returns:
            int: Number of deleted rows.
        """
        ...



class SQLSessionRepository(BaseSessionRepository):
    """Implementation of host storage using Peewee ORM."""
    
    def create(self, user_email: str, created_at: datetime, valid_until: datetime) -> SessionRecord:
        try:
            session = SessionRecord.create(
                id=uuid.uuid4(),
                created_at=created_at,
                valid_until=valid_until,
                user=user_email,
            )
            return session
        except IntegrityError as e:
            raise ConflictError(f"failed to create Session: {e}")
        except Exception as e:
            raise ServiceError(f"unexpected error while creating a new Session: {e}")


    def read(self, **filters) -> list[SessionRecord]:
        query = SessionRecord.select()
        for field, value in filters.items():
            query = query.where(getattr(SessionRecord, field) == value)
        return list(query)


    def update(self, uuid: uuid.UUID, **fields) -> SessionRecord:
        rows = (SessionRecord
                    .update(**fields)
                    .where(SessionRecord.id == uuid)
                    .execute())
        if rows == 0:
            raise NotFoundError(f"Session {uuid} does not exist")
        return SessionRecord.get_by_id(uuid)


    def delete(self, uuid: uuid.UUID) -> SessionRecord:
        record = SessionRecord.get_or_none(SessionRecord.id == uuid)
        if record is None:
            raise NotFoundError(f"Session {uuid} does not exist")

        rows_deleted = (SessionRecord
                        .delete()
                        .where(SessionRecord.id == uuid)
                        .execute())
        if rows_deleted == 0:
            raise NotFoundError(f"Session {uuid} does not exist")
        return record


    def delete_expired(self, now: datetime) -> int:
        rows_deleted = (SessionRecord
                        .delete()
                        .where(SessionRecord.valid_until < now)
                        .execute())
        return int(rows_deleted)