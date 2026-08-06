from abc import ABC, abstractmethod

from peewee import IntegrityError

from ..exceptions.errors import ConflictError, NotFoundError, ServiceError
from ..utils.models import Host


class BaseHostRepository(ABC):
    """A base class for managing host parameters stored in persistent storage"""

    @abstractmethod
    def create(self, ip: str, mac: str, config: dict) -> Host:
        """
        Creates a new host record.

        Args:
            ip: Host IP address.
            mac: Host MAC address.
            config: JSON-serialized HostConfig.

        Returns:
            Host: The newly created Host instance.

        Raises:
            ConflictError: If the host already exists.
            ServiceError: If an unexpected error occurs.
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
            NotFoundError: If the host does not exist.
        """
        ...

    @abstractmethod
    def delete(self, ip: str) -> None:
        """
        Removes a host record by IP.

        Args:
            ip: The IP address of the host to remove.

        Raises:
            NotFoundError: If the host does not exist.
        """
        ...



class SQLHostRepository(BaseHostRepository):
    """
    Implementation of host storage using Peewee ORM.
    """

    def create(self, ip: str, mac: str, config: dict) -> Host:
        try:
            return Host.create(ip=ip, mac=mac, config=config)
        except IntegrityError as e:
            raise ConflictError(f"failed to add host: {e}")
        except Exception as e:
            raise ServiceError(f"unexpected error while creating a new host: {e}")


    def read(self, **filters) -> list[Host]:
        query = Host.select()
        for field, value in filters.items():
            if value is None:
                continue
            query = query.where(getattr(Host, field) == value)
        return list(query)


    def update(self, ip: str, **fields) -> Host:
        rows = (Host
                    .update(**fields)
                    .where(Host.ip == ip)
                    .execute())
        if rows == 0:
            raise NotFoundError(f"host {ip} does not exist")
        return Host.get_by_id(ip)


    def delete(self, ip: str) -> None:
        query = Host.delete().where(Host.ip == ip)
        rows_deleted = query.execute()
        if rows_deleted == 0:
            raise NotFoundError(f"host {ip} does not exist")
