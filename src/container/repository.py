from abc import ABC, abstractmethod
import threading


from ..utils.csv_storage import CSVParams, CSVStorage
from ..utils.sql_models import Container
from ..utils.keygen import KeyGenerator
from ..utils.logger import logger


class BaseContainerRepository(ABC):
    """A base class for managing container parameters stored in a file"""
    
    @abstractmethod
    def __init__(self, keyGenerator: KeyGenerator) -> None:
        self.key = keyGenerator
    

    @abstractmethod
    def create(self, ip: str, port: int) -> str:
        """Add a new container to the file and return it's assigned subdomain."""
        ...
    
    @abstractmethod
    def read(self, subdomain: str) -> tuple[str, int]:
        """Get the container with specified subdomain."""
        ...
    
    @abstractmethod
    def delete(self, subdomain: str) -> None:
        """Remove the container with specified subdomain."""
        ...
    
    def dict(self) -> dict[str, dict[str, str | int]]:
        """Return stored containers in JSON friendly format."""
        ...



class CSVContainerRepository(BaseContainerRepository):

    def __init__(self, params: CSVParams, keyGenerator: KeyGenerator) -> None:
        super().__init__(keyGenerator)
        self.params = params
        self.storage = CSVStorage(params)

        self.lock = threading.Lock()
        self.cache: dict[str, tuple[str, int]] = {}
        
        try:
            rows = self.storage.read_rows()
        except:
            logger.exception(f"failed to load rows when caching {self.params.path}")
        else:
            with self.lock:
                for row in rows:
                    self.cache.setdefault(row["subdomain"], (row["ip"], int(row["port"])))


    def create(self, ip: str, port: int) -> str:
        with self.lock:
            for existing_ip, existing_port in self.cache.values():
                if existing_ip == ip and existing_port == port:
                    raise KeyError(f"container with ip={ip}, port={port} already exists")

        key =  self.key.gen()

        try:
            self.storage.insert({
                "subdomain": key,
                "ip": ip,
                "port": port
            })
        except:
            logger.exception(f"failed to add {ip}:{port} to container storage")
            return ""
        else:
            with self.lock:
                self.cache.setdefault(key, (ip, port))
            return key


    def read(self, subdomain: str) -> tuple[str, int]:
        with self.lock:
            if subdomain not in self.cache:
                raise KeyError(f"container {subdomain} does not exist")
            return self.cache[subdomain]


    def delete(self, subdomain: str) -> None:
        with self.lock:
            if subdomain not in self.cache:
                raise KeyError(f"container {subdomain} does not exist")
        
        try:
            with self.lock:
                ip, port = self.cache[subdomain]
            self.storage.delete({
                "subdomain": subdomain,
                "ip": ip,
                "port": int(port)
            })
        except Exception:
            logger.error(f"failed to remove {subdomain}, file and dictionary were restored")
        else:
            with self.lock:
                del self.cache[subdomain]


    def dict(self) -> dict[str, dict[str, str | int]]:
        with self.lock:
            temp = self.cache.items()
        return {subd: {"ip": v[0], "port": v[1]} for subd, v in temp}
    


class SQLContainerRepository(BaseContainerRepository):
    """
    Implementation of storage using Django ORM.
    """

    def __init__(self, keyGenerator: KeyGenerator) -> None:
        super().__init__(keyGenerator)
        
         
    def create(self, ip: str, port: int) -> str:
        try:
            new_key = self.key.gen()
            container: Container = Container.create(
                subdomain=new_key,
                host=ip,
                port=port
            )
            return str(container.subdomain)
        except Exception as e:
            raise RuntimeError(f"failed to create container {ip}:{port}: {e}")
        

    def read(self, subdomain: str) -> tuple[str, int]:
        query = (Container
                    .select(Container.host, Container.port)
                    .where(Container.subdomain == subdomain))
        
        if not query.exists():
            raise KeyError(f"container {subdomain} does not exist")
        
        return query[0].host.ip, query[0].port
    

    def delete(self, subdomain: str) -> None:
        """Remove the container with specified subdomain."""
        query = (Container
                    .delete()
                    .where(Container.subdomain == subdomain))
        
        rows_deleted = query.execute()
        
        if rows_deleted == 0:
            raise KeyError(f"container {subdomain} does not exist")
        

    def dict(self) -> dict[str, dict[str, str | int]]:
        """Return stored containers in JSON friendly format."""
        query = Container.select()

        return {c.subdomain: {"ip": c.host_id, "port": c.port} for c in query}