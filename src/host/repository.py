from abc import ABC, abstractmethod
from ..utils.models import Host
from peewee import IntegrityError


class BaseHostRepository(ABC):
    """A base class for managing host parameters stored in persistent storage"""
    
    @abstractmethod
    def create(self, ip: str, mac: str, user: str, path: str) -> None:
        """
        Creates a new host record.

        Args:
            ip: Host IP address.
            mac: Host MAC address.
            user: SSH username.
            path: Base path on the host.

        Raises:
            KeyError: If the host already exists.
            RuntimeError: If an unexpected error occurs.
        """
        ...
    
    @abstractmethod
    def read(self, ip: str) -> tuple[str, str, str]:
        """
        Retrieves host details by IP.

        Args:
            ip: The IP address to look up.

        Returns:
            tuple[str, str, str]: A tuple containing (mac, user, path).

        Raises:
            KeyError: If the host does not exist.
        """
        ...
    
    @abstractmethod
    def delete(self, ip: str) -> None:
        """
        Removes a host record by IP.

        Args:
            ip: The IP address of the host to remove.

        Raises:
            KeyError: If the host does not exist.
        """
        ...
    
    def list(self) -> list[dict[str, str]]:
        """
        Returns all stored hosts in a JSON-friendly format.

        Returns:
             list[dict[str, str]]: List of host dictionaries.
        """
        ...



class HostRepository(BaseHostRepository):
    """
    Implementation of host storage using Peewee ORM.
    """
    
    def create(self, ip: str, mac: str, user: str, path: str) -> None:
        try:
            Host.create(ip=ip, mac=mac, user=user, path=path)
        except (KeyError, IntegrityError) as e:
            raise KeyError(f"failed to add host: {e}")
        except Exception as e:
            raise RuntimeError(f"unexpected error while creating a new host: {e}")

    
    def read(self, ip: str) -> tuple[str, str, str]:

        host = Host.get_or_none(Host.ip == ip)
        if host is None:
             raise KeyError(f"host {ip} does not exist")
        return host.mac, host.user, host.path

    
    def delete(self, ip: str) -> None:

        query = Host.delete().where(Host.ip == ip)
        rows_deleted = query.execute()
        if rows_deleted == 0:
             raise KeyError(f"host {ip} does not exist")
    

    def list(self) -> list[dict[str, str]]:
        hosts = Host.select()
        return [{
                "ip": h.ip,
                "mac": h.mac,
                "user": h.user,
                "path": h.path
            } for h in hosts
        ]