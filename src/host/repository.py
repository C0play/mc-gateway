from abc import ABC, abstractmethod
from ..utils.models import Host
from peewee import IntegrityError


class BaseHostRepository(ABC):
    """A base class for managing container parameters stored in a file"""
    
    @abstractmethod
    def create(self, ip: str, mac: str, user: str, path: str) -> None:
        """Add row with specified fields to file."""
        ...
    
    @abstractmethod
    def read(self, ip: str) -> tuple[str, str, str]:
        """Get a row, where the first field value matches ip."""
        ...
    
    @abstractmethod
    def delete(self, ip: str) -> None:
        """Remove a row, where the first field value matches ip."""
        ...
    
    def dict(self) -> list[dict[str, str]]:
        """Return file contents in JSON friendly format."""
        ...



class HostRepository(BaseHostRepository):
    """A class for managing host parameters stored in a postgres database"""
    
    def create(self, ip: str, mac: str, user: str, path: str) -> None:
        """Add row with specified fields to file."""

        try:
            Host.create(ip=ip, mac=mac, user=user, path=path)
        except IntegrityError as e:
            msg = str(e).lower()
            if "ip" in msg:
                raise KeyError(f"host {ip} already exists")
            elif "mac" in msg:
                raise KeyError(f"host with mac={mac} already exists")
            else:
                 raise KeyError(f"host {ip} or mac {mac} already exists: {e}")
        except Exception as e:
            raise KeyError(f"failed to add host {ip}: {e}")

    
    def read(self, ip: str) -> tuple[str, str, str]:
        """Get a row, where the first field value matches ip."""

        host = Host.get_or_none(Host.ip == ip)
        if host is None:
             raise KeyError(f"host {ip} does not exist")
        return host.mac, host.user, host.path

    
    def delete(self, ip: str) -> None:
        """Remove a row, where the first field value matches ip."""

        query = Host.delete().where(Host.ip == ip)
        rows_deleted = query.execute()
        if rows_deleted == 0:
             raise KeyError(f"host {ip} does not exist")
    

    def dict(self) -> list[dict[str, str]]:
        """Return file contents in JSON friendly format."""

        hosts = Host.select()
        return [{
                "ip": h.ip,
                "mac": h.mac,
                "user": h.user,
                "path": h.path
            } for h in hosts
        ]