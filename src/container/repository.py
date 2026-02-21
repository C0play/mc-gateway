from abc import ABC, abstractmethod


from ..utils.models import Container
from ..utils.keygen import KeyGenerator


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
    
    def dict(self) -> list[dict[str, str]]:
        """Return stored containers in JSON friendly format."""
        ...



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
        

    def dict(self) -> list[dict[str, str]]:
        """Return stored containers in JSON friendly format."""

        query = Container.select()
        return [{
                "subdomain": c.subdomain, 
                "ip": c.host_id,
                "port": str(c.port)
            } for c in query
        ]