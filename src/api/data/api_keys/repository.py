from abc import ABC, abstractmethod
import datetime

from peewee import IntegrityError

from ....utils.models import ApiKey
from ....exceptions.errors import NotFoundError, ServiceError
from ....security.hashing import sha256_hex
from ....security.tokens import generate_token_urlsafe



class BaseKeyRepository(ABC):
    """A base class for managing whitelist parameters stored in persistent storage"""
    
    @abstractmethod
    def create(self, user_email: str) -> str:
        """
        Registeres an APiKey for a user.

        Args:
            user_email: The users's email.

        Returns:
            api_key: Unhashed API key (keys are hashed at rest).

        Raises:
            NotFoundError: If the user with the specified email does not exist.
        """
        ...
    
    @abstractmethod
    def read(self, **filters) -> list[ApiKey]:
        """
        Retrieves APiKey records matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[APiKey]: Matching APiKey model instances.
        """
        ...

    @abstractmethod
    def read_from_unhashed_key(self, api_key: str) -> ApiKey:
        """
        Retrieves APiKey record based on the provided unhashed key.

        Args:
             api_key: Unhashed API key.

        Returns:
            APiKey: APiKey model instances.
        """
        ...
    
    @abstractmethod
    def update(self, api_key: str, **fields) -> ApiKey:
        """
        Updates arbitrary fields on a ApiKey record.

        Args:
            key: The hashed api key of the user.
            **fields: Field names and their new values.

        Returns:
            ApiKey: The updated ApiKey instance.

        Raises:
            NotFoundError: If the api_key does not exist.
        """
        ...

    @abstractmethod
    def delete(self, api_key: str,) -> ApiKey:
        """
        Removes an ApiKey record.

        Args:
            key: The unhashed key to remove.

        Raises:
            NotFoundError: If the api key does not exist.
        """
        ...



class SQLKeyRepository(BaseKeyRepository):
    """
    Implementation of host storage using Peewee ORM.
    """
    
    def create(self, user_email: str) -> str:
        try:
            plain_key = generate_token_urlsafe(32)
            hashed_key = sha256_hex(plain_key)
            today = datetime.datetime.today()
            ApiKey.create(
                key_hash=hashed_key,
                created_at=today,
                last_used_at=today,
                user=user_email,
            )
            return plain_key
        except IntegrityError as e:
            raise NotFoundError(f"user {user_email} does not exist: {e}")
        except Exception as e:
            raise ServiceError(f"unexpected error while creating a new API key: {e}")


    def read(self, **filters) -> list[ApiKey]:
        query = ApiKey.select()
        for field, value in filters.items():
            if value is None:
                continue
            query = query.where(getattr(ApiKey, field) == value)
        return list(query)


    def read_from_unhashed_key(self, api_key: str) -> ApiKey:
        key_hash = sha256_hex(api_key)
        record = (ApiKey
                    .select()
                    .where(ApiKey.key_hash == key_hash)
                    .first())
        if record is None:
            raise NotFoundError("API key does not exist")
        return record
        

    def update(self, api_key: str, **fields) -> ApiKey:
        rows = (ApiKey
                    .update(**fields)
                    .where(ApiKey.key_hash == api_key)
                    .execute())
        if rows == 0:
            raise NotFoundError(f"API key does not exist")
        return ApiKey.get(ApiKey.key_hash == api_key)


    def delete(self, api_key: str,) -> ApiKey:
        key_hash = sha256_hex(api_key)
        record = ApiKey.get_or_none(ApiKey.key_hash == key_hash)
        if record is None:
            raise NotFoundError(f"API key does not exist")

        rows_deleted = (ApiKey
                        .delete()
                        .where(ApiKey.key_hash == key_hash)
                        .execute())
        if rows_deleted == 0:
            raise NotFoundError(f"API key does not exist")
        return record