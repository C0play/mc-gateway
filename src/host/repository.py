from abc import ABC, abstractmethod
from ..utils.models import Host
from peewee import IntegrityError


class BaseHostRepository(ABC):
    """A base class for managing host parameters stored in persistent storage"""
    
    @abstractmethod
    def create(self, ip: str, mac: str, user: str, path: str) -> Host:
        """
        Creates a new host record.

        Args:
            ip: Host IP address.
            mac: Host MAC address.
            user: SSH username.
            path: Base path on the host.

        Returns:
            Host: The newly created Host instance.

        Raises:
            KeyError: If the host already exists.
            RuntimeError: If an unexpected error occurs.
        """
        ...
    
    @abstractmethod
    def read(self, **filters) -> list[Host]:
        """
        Retrieves host records matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[Host]: Matching Host model instances.
        """
        ...
    
    @abstractmethod
    def update(self, ip: str, **fields) -> Host:
        """
        Updates arbitrary fields on a host record.

        Args:
            ip: The IP of the host.
            **fields: Field names and their new values.

        Returns:
            Host: The updated Host instance.

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



class SQLHostRepository(BaseHostRepository):
    """
    Implementation of host storage using Peewee ORM.
    """
    
    def create(self, ip: str, mac: str, user: str, path: str) -> Host:
        try:
            return Host.create(ip=ip, mac=mac, user=user, path=path)
        except (KeyError, IntegrityError) as e:
            raise KeyError(f"failed to add host: {e}")
        except Exception as e:
            raise RuntimeError(f"unexpected error while creating a new host: {e}")


    def read(self, **filters) -> list[Host]:
        query = Host.select()
        for field, value in filters.items():
            query = query.where(getattr(Host, field) == value)
        return list(query)


    def update(self, ip: str, **fields) -> Host:
        rows = (Host
                    .update(**fields)
                    .where(Host.ip == ip)
                    .execute())
        if rows == 0:
            raise KeyError(f"host {ip} does not exist")
        return Host.get_by_id(ip)


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