from abc import ABC, abstractmethod

import peewee as pewe

from ..exceptions.errors import ConflictError, NotFoundError, ServiceError
from ..utils.logger import logger
from ..utils.models import Container, Whitelist


class BaseWhitelistRepository(ABC):
    """A base class for managing whitelist parameters stored in persistent storage"""

    @abstractmethod
    def create(self, username: str, subdomain: str) -> Whitelist:
        """
        Adds a player to a server's whitelist.

        Args:
            username: The player's username.
            subdomain: The server's subdomain.

        Returns:
            Whitelist: The newly created Whitelist instance.

        Raises:
            NotFoundError: If the container does not exist.
            ConflictError: If the player is already whitelisted.
        """
        ...

    @abstractmethod
    def read(self, **filters) -> list[Whitelist]:
        """
        Retrieves whitelist records matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[Whitelist]: Matching Whitelist model instances.
        """
        ...

    @abstractmethod
    def exists(self, fields: dict[str, str]) -> bool:
        """
        Checks if a whitelist entry matching the given fields exists.

        Args:
             fields: Dictionary of fields to filter by (username, subdomain/container).

        Returns:
             bool: True if a matching entry exists, False otherwise.
        """
        ...

    @abstractmethod
    def delete(self, username: str, subdomain: str) -> None:
        """
        Removes a player from a server's whitelist.

        Args:
            username: The player's username.
            subdomain: The server's subdomain.

        Raises:
            NotFoundError: If the whitelist entry does not exist.
        """
        ...



class SQLWhitelistRepository(BaseWhitelistRepository):
    """
    Implementation of whitelist storage using Peewee ORM.
    """

    def create(self, username: str, subdomain: str) -> Whitelist:
        try:
            return Whitelist.create(
                username=username,
                container=subdomain
            )
        except pewe.IntegrityError:
            if not Container.select().where(Container.subdomain == subdomain).exists():
                 raise NotFoundError(f"container {subdomain} does not exist")
            raise ConflictError(f"player {username} is already whitelisted on {subdomain}")
        except Exception as e:
            raise ServiceError(f"failed to add player {username} to {subdomain}: {e}")


    def read(self, **filters) -> list[Whitelist]:
        query = Whitelist.select()
        for field, value in filters.items():
            if value is None:
                continue
            query = query.where(getattr(Whitelist, field) == value)
        return list(query)


    def exists(self, fields: dict[str, str]) -> bool:
        if not fields:
            return Whitelist.select().exists()

        expressions = []
        for key, value in fields.items():
            if key == "subdomain":
                key = "container"

            if hasattr(Whitelist, key) :
                expressions.append(getattr(Whitelist, key) == value)
            else:
                return False

        if not expressions:
            return False
        res = Whitelist.select().where(*expressions).exists()
        logger.debug(f"{res} {fields}")
        return res



    def delete(self, username: str, subdomain: str) -> None:

        query = (Whitelist
                    .delete()
                    .where((Whitelist.username == username) & (Whitelist.container == subdomain))
                )
        rows_deleted = query.execute()

        if rows_deleted == 0:
            raise NotFoundError(f"player {username} does not exist or is not whitelisted on {subdomain}")
