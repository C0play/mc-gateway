import datetime
from abc import ABC, abstractmethod

from peewee import IntegrityError

from ....exceptions.errors import NotFoundError, ServiceError
from ....security.hashing import sha256_hex
from ....security.tokens import generate_token_urlsafe
from ....utils.models import ApiKey
from ..mappers.api_key import apikey_from_record
from ..models.api_key import ApiKey as ApiKeyModel


class BaseKeyRepository(ABC):
    """A base class for managing api keys stored in persistent storage"""

    @abstractmethod
    def create(self, email: str, name: str) -> str:
        """
        Registers an ApiKey with the specified name for a user.

        Args:
            email: The users's email.
            name: Name for the key.

        Returns:
            str: Unhashed API key (keys are hashed at rest).

        Raises:
            NotFoundError: If the user with the specified email does not exist.
        """
        ...

    @abstractmethod
    def read(self, **filters) -> list[ApiKeyModel]:
        """
        Retrieves ApiKeys matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[ApiKeyModel]: Matching ApiKey model instances.
        """
        ...

    @abstractmethod
    def read_from_unhashed_key(self, key: str) -> ApiKeyModel:
        """
        Retrieves an ApiKey from the provided unhashed key.

        Args:
            key: Unhashed API key.

        Returns:
            ApiKeyModel: ApiKey model instance.

        Raises:
            NotFoundError: If the api key does not exist.
        """
        ...

    @abstractmethod
    def update(self, email: str, name: str, **fields) -> ApiKeyModel:
        """
        Updates arbitrary fields on an ApiKey record.

        Args:
            email: The key's owner's email address.
            name: The key's name.
            **fields: Field names and their new values.

        Returns:
            ApiKeyModel: The updated ApiKey instance.

        Raises:
            NotFoundError: If the api key does not exist.
        """
        ...

    @abstractmethod
    def delete(self, email: str, name: str) -> ApiKeyModel:
        """
        Removes an ApiKey record.

        Args:
            email: The key's owner's email address.
            name: The key's name.

        Raises:
            NotFoundError: If the api key does not exist.
        """
        ...


class SQLKeyRepository(BaseKeyRepository):
    """
    Implementation of api key storage using Peewee ORM.
    """

    def create(self, email: str, name: str) -> str:
        try:
            plain_key = generate_token_urlsafe(32)
            hashed_key = sha256_hex(plain_key)
            today = datetime.datetime.today()
            ApiKey.create(
                key_hash=hashed_key,
                created_at=today,
                last_used_at=today,
                user=email,
                name=name,
            )
            return plain_key
        except IntegrityError as e:
            raise NotFoundError(f"user {email} does not exist: {e}")
        except Exception as e:
            raise ServiceError(f"unexpected error while creating a new API key: {e}")

    def read(self, **filters) -> list[ApiKeyModel]:
        query = ApiKey.select()
        for field, value in filters.items():
            if value is None:
                continue
            query = query.where(getattr(ApiKey, field) == value)
        return [apikey_from_record(r) for r in list(query)]

    def read_from_unhashed_key(self, key: str) -> ApiKeyModel:
        key_hash = sha256_hex(key)
        return self._read_one(key_hash=key_hash)

    def update(self, email: str, name: str, **fields) -> ApiKeyModel:
        rows = (
            ApiKey.update(**fields)
            .where(ApiKey.user == email, ApiKey.name == name)
            .execute()
        )
        if rows == 0:
            raise NotFoundError("API key does not exist")

        return self._read_one(user=email, name=name)

    def delete(self, email: str, name: str) -> ApiKeyModel:
        key = self._read_one(user=email, name=name)
        deleted_count = (
            ApiKey.delete().where(ApiKey.user == email, ApiKey.name == name).execute()
        )
        if deleted_count == 0:
            raise NotFoundError(f"API key does not exist")

        return key

    def _read_one(self, **filters) -> ApiKeyModel:
        keys = self.read(**filters)
        if not keys or len(keys) > 1:
            raise NotFoundError("API key does not exist or multiple records match")
        return keys[0]
