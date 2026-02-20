from abc import ABC, abstractmethod
from ..utils.sql_models import Host
import peewee as pewe
import threading

from ..utils.csv_storage import CSVParams, CSVStorage
from ..utils.logger import logger


class BaseHostRepository(ABC):
    """A base class for managing container parameters stored in a file"""
    
    @abstractmethod
    def add(self, ip: str, mac: str, user: str, path: str) -> None:
        """Add row with specified fields to file."""
        ...
    
    @abstractmethod
    def get(self, ip: str) -> tuple[str, str, str]:
        """Get a row, where the first field value matches ip."""
        ...
    
    @abstractmethod
    def remove(self, ip: str) -> None:
        """Remove a row, where the first field value matches ip."""
        ...
    
    def dict(self) -> dict[str, dict[str, str | int]]:
        """Return file contents in JSON friendly format."""
        ...



class CSVHostRepository(BaseHostRepository):

    def __init__(self, params: CSVParams) -> None:
        self.params = params
        self.storage = CSVStorage(params)

        self.lock = threading.Lock()
        self.cache: dict[str, tuple[str, str, str]] = {} # ip -> mac, user, path
        
        try:
            rows = self.storage.read_rows()
        except:
            logger.exception(f"failed to load rows when caching {self.params.path}")
        else:
            with self.lock:
                for row in rows:
                    self.cache.setdefault(row["ip"], (row["mac"], row["user"], row["path"]))


    def add(self, ip: str, mac: str, user: str, path: str) -> None:
        with self.lock:
            if ip in self.cache:
                raise KeyError(f"host {ip} already exists")
            for existing_mac in self.cache.values():
                if existing_mac == mac:
                    raise KeyError(f"host with mac={mac} already exists")

        try:
            self.storage.insert({
                "ip": ip,
                "mac": mac,
                "user": user,
                "path": path
            })
        except:
            logger.exception(f"failed to add {ip} to host storage")
        else:
            with self.lock:
                self.cache.setdefault(ip, (mac, user, path))


    def get(self, ip: str) -> tuple[str, str, str]:
        with self.lock:
            if ip not in self.cache:
                raise KeyError(f"host {ip} does not exist")
            return self.cache[ip]


    def remove(self, ip: str) -> None:
        with self.lock:
            if ip not in self.cache:
                raise KeyError(f"host {ip} does not exist")
            
            mac, user, path = self.cache[ip]

        try:
            self.storage.delete({
                "ip": ip,
                "mac": mac,
                "user": user,
                "path": path
            })
        except:
            logger.exception(f"failed to remove {ip}, file and dictionary were restored")
        else:
            with self.lock:
                del self.cache[ip]


    def dict(self) -> dict[str, dict[str, str | int]]:
        with self.lock:
            temp = self.cache.items()
        return {ip: {"mac": mac, "user": user, "path": path} 
                for ip, (mac, user, path) in temp}
    


class SQLHostStorage(BaseHostRepository):
    """A class for managing host parameters stored in a postgres database"""
    
    def add(self, ip: str, mac: str, user: str, path: str) -> None:
        """Add row with specified fields to file."""
        try:
            Host.create(ip=ip, mac=mac, user=user, path=path)
        except pewe.IntegrityError as e:
            msg = str(e).lower()
            if "ip" in msg:
                raise KeyError(f"host {ip} already exists")
            elif "mac" in msg:
                raise KeyError(f"host with mac={mac} already exists")
            else:
                 raise KeyError(f"host {ip} or mac {mac} already exists: {e}")
        except Exception as e:
            raise KeyError(f"failed to add host {ip}: {e}")

    
    def get(self, ip: str) -> tuple[str, str, str]:
        """Get a row, where the first field value matches ip."""
        host = Host.get_or_none(Host.ip == ip)
        if host is None:
             raise KeyError(f"host {ip} does not exist")
        return host.mac, host.user, host.path

    
    def remove(self, ip: str) -> None:
        """Remove a row, where the first field value matches ip."""
        query = Host.delete().where(Host.ip == ip)
        rows_deleted = query.execute()
        if rows_deleted == 0:
             raise KeyError(f"host {ip} does not exist")
    
    def dict(self) -> dict[str, dict[str, str | int]]:
        """Return file contents in JSON friendly format."""
        hosts = Host.select()
        return {h.ip: {"mac": h.mac, "user": h.user, "path": h.path} for h in hosts}