from ipaddress import ip_address
from typing import cast

from ....utils.models import Container as ContainerRecord
from ..models.container import ContainerConfig, FullContainer


def full_container_from_record(record: ContainerRecord) -> FullContainer:
    """Maps a container record to it's full pydantic model."""

    ip = "127.0.0.1" if record.host is None else record.host.ip
    return FullContainer(
        subdomain=str(record.subdomain),
        ip=ip_address(ip),
        owner=str(record.owner),
        config=ContainerConfig.model_validate(record.config),
        to_be_deleted=cast(bool, record.to_be_deleted),
        initialized=cast(bool, record.initialized),
    )
