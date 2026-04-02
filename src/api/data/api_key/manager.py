from abc import ABC, abstractmethod

from ....exceptions.errors import NotFoundError
from .repository import BaseKeyRepository, SQLKeyRepository
from ....utils.models import ApiKey

class BaseKeyManager(ABC):


    def __init__(self, key_repository: BaseKeyRepository) -> None:
        self.keys = key_repository

    @abstractmethod
    def create(self, user_email: str) -> str:
        """
        Creates a new key for the user.

        Args:
            user_email: Email address of the user to create the key for.

        Returns:
            str: Unhashed API key of the user.

        Raises:
            NotFoundError: If the user with the specified email does not exist.
        """
    
    @abstractmethod
    def read(self, **filters) -> list[ApiKey]:
        """
        Returns all APiKey records matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[APiKey]: Matching APiKey model instances.
        """
        ...

    @abstractmethod
    def read_from_unhashed_key(self, key: str) -> ApiKey:
        """
        Retrieves APiKey record based on the provided unhashed key.

        Args:
             api_key: Unhashed API key.

        Returns:
            APiKey: APiKey model instances.
        """
        ...

    @abstractmethod
    def deactivate(self, email: str, name: str) -> None:
        """
        Marks the api key as inactive.

        Args:
            email: API key owner's email address.
            name: API key's name.

        Raises:
            NotFoundError: If the API key does not exist.
        """

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Deletes the api key permanently.

        Args:
            key: API key to delete.

        Raises:
            NotFoundError: If the API key does not exist.
        """
    
    

class SQLKeyManager(BaseKeyManager):
    
    def __init__(self, key_repository: SQLKeyRepository) -> None:
        super().__init__(key_repository)
    
    
    def create(self, user_email: str) -> str:
        return self.keys.create(user_email)
    
    def read(self, **filters) -> list[ApiKey]:
        return self.keys.read(**filters)

    def read_from_unhashed_key(self, key: str) -> ApiKey:
        return self.keys.read_from_unhashed_key(key)

    def deactivate(self, email: str, name: str) -> None:
        records = self.keys.read(user=email, name=name)
        if not records:
            raise NotFoundError(f"key {name} does not exist")
        
        key_hash = str(records[0].key_hash)
        self.keys.update(key_hash, active=False)

    def delete(self, key: str) -> None:
        self.keys.delete(key)



    