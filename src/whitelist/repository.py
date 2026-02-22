from abc import ABC, abstractmethod
import peewee as pewe
from peewee import fn

from ..utils.logger import logger
from ..utils.models import Whitelist, Container



class BaseWhitelistRepository(ABC):
    """A base class for managing whitelist parameters stored in persistent storage"""
    
    @abstractmethod
    def create(self, username: str, subdomain: str) -> None:
        """
        Adds a player to a server's whitelist.

        Args:
            username: The player's username.
            subdomain: The server's subdomain.

        Raises:
            KeyError: If the container does not exist or the player is already whitelisted.
        """
        ...
    
    @abstractmethod
    def read(self, username: str) -> list[str]:
        """
        Retrieves all subdomains a player is whitelisted on.

        Args:
            username: The player's username.

        Returns:
            list[str]: A list of subdomains.

        Raises:
            KeyError: If the player does not exist (is not whitelisted anywhere).
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
            KeyError: If the whitelist entry does not exist.
        """
        ...
    
    def list(self) -> list[dict[str, list[str]]]:
        """
        Returns the contents of the whitelist in a JSON-friendly format.

        Returns:
             list[dict[str, list[str]]]: List of user-subdomains mappings.
        """
        ...



class WhitelistRepository(BaseWhitelistRepository):
    """
    Implementation of whitelist storage using Peewee ORM.
    """

    def create(self, username: str, subdomain: str) -> None:
        try:
            Whitelist.create(
                username=username,
                container=subdomain
            )
        except pewe.IntegrityError:
            if not Container.select().where(Container.subdomain == subdomain).exists():
                 raise KeyError(f"container {subdomain} does not exist")
            raise KeyError(f"player {username} is already whitelisted on {subdomain}")

    
    def read(self, username: str) -> list[str]:
        query = (Whitelist
                    .select(Whitelist.container)
                    .where(Whitelist.username == username))
        
        if not query.exists():
             raise KeyError(f"player {username} does not exist")

        return [w.container.id for w in query]


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
            raise KeyError(f"player {username} does not exist or is not whitelisted on {subdomain}")


    def list(self) -> list[dict[str, list[str]]]:
        query = (Whitelist
                .select(
                    Whitelist.username,
                    fn.array_agg(Whitelist.container).alias('subdomains')
                )
                .group_by(Whitelist.username))
        
        return [{
            "username": row.username,
            "subdomains": list(row.subdomains)
            } for row in query
        ]