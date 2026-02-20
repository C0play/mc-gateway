from abc import ABC, abstractmethod
import threading

from ..utils.csv_storage import CSVParams, CSVStorage
from ..utils.logger import logger

from ..utils.sql_models import Whitelist, Container
import peewee as pewe



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
    
    def dict(self) -> dict[str, dict[str, list[str]]]:
        """Returns the contents of the file in JSON friendly format."""
        ...



class CSVWhitelistRepository(BaseWhitelistRepository):

    def __init__(self, storageParams: CSVParams) -> None:
        self.storage = CSVStorage(storageParams)

        self.lock = threading.Lock()
        self.cache: dict[str, list[str]] = {} # username -> server_subdomains
        
        try:
            rows = self.storage.read_rows()
        except:
            logger.exception(f"failed to read rows when caching {storageParams.path}")
        else:
            with self.lock:
                for row in rows:
                    if row["username"] not in self.cache:
                        self.cache[row["username"]] = [row["subdomain"]]
                    else:
                        self.cache[row["username"]].append(row["subdomain"])


    def create(self, username: str, subdomain: str) -> None:
        with self.lock:
            if username in self.cache and subdomain in self.cache[username]:
                raise KeyError(f"player {username} is already whitelisted on {subdomain}")
            
        try:
            self.storage.insert({"username": username, "subdomain": subdomain})
        except:
            logger.exception(f"failed to remove {username}:{subdomain} from storage")
        else:
            with self.lock:
                if username in self.cache:
                    self.cache[username].append(subdomain)
                else:
                    self.cache[username] = [subdomain]

        
    def read(self, username: str) -> list[str]:
        with self.lock:
            if username not in self.cache:
                raise KeyError(f"player {username} does not exist")
            
            return self.cache[username]


    def exists(self, fields: dict[str, str]) -> bool:
        try:
            res = self.storage.select(fields)
        except:
            logger.exception(f"failed to search for {fields} in storage")
            raise
        else:
            return True if res else False


    def delete(self, username: str, subdomain: str) -> None:
        with self.lock:
            if not (username in self.cache and subdomain in self.cache[username]):
                raise KeyError(f"player {username} does not exist or is not whitelisted on {subdomain}")
        
        try:
            self.storage.delete({"username": username, "subdomain": subdomain})
        except Exception as e:
            logger.error(f"failed to remove {username}:{subdomain} from storage: {e}")
        else:
            with self.lock:
                self.cache[username].remove(subdomain)
                if not self.cache[username]:
                    del self.cache[username]


    def dict(self) -> dict[str, dict[str, list[str]]]:
        with self.lock:
            temp = self.cache.keys()
            
        return {username: {"subdomains": self.cache[username]} for username in temp}
    


class SQLWhitelistRepository(BaseWhitelistRepository):


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

        return Whitelist.select().where(*expressions).exists()



    def delete(self, username: str, subdomain: str) -> None:
        query = (Whitelist.delete()
                    .where((Whitelist.username == username) 
                            & (Whitelist.container == subdomain)
                    )
                )
        rows_deleted = query.execute()
        
        if rows_deleted == 0:
            raise KeyError(f"player {username} does not exist or is not whitelisted on {subdomain}")


    def dict(self) -> dict[str, dict[str, list[str]]]:
        """Returns the contents of the file in JSON friendly format."""
        items = Whitelist.select()
        
        result = {}
        for item in items:
            user = item.username
            sub = item.container_id
            
            if user not in result:
                result[user] = {"subdomains": []}
            result[user]["subdomains"].append(sub)
            
        return result