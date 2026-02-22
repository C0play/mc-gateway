from abc import ABC, abstractmethod
import peewee as pewe
from peewee import fn

from ..utils.logger import logger
from ..utils.models import Whitelist, Container



class BaseWhitelistRepository(ABC):
    """A base class for managing container parameters stored in a file"""
    
    @abstractmethod
    def create(self, username: str, subdomain: str) -> None:
        """Add row: "username","subdomain" to the file. If a row with specified
        fields already exists, raises a KeyError."""
        ...
    
    @abstractmethod
    def read(self, username: str) -> list[str]:
        """Returns a list of subdomains, where the first fields in username."""
        ...
    
    @abstractmethod
    def exists(self, fields: dict[str, str]) -> bool:
        """Returns True if a row with all specified fields exists and the value
        in each field matches the provided value."""
        ...

    @abstractmethod
    def delete(self, username: str, subdomain: str) -> None:
        """Remove the row with specified values"""
        ...
    
    def dict(self) -> list[dict[str, list[str]]]:
        """Returns the contents of the file in JSON friendly format."""
        ...



class WhitelistRepository(BaseWhitelistRepository):


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


    def dict(self) -> list[dict[str, list[str]]]:
        """Returns the contents of the database in JSON friendly format."""
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