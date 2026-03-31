from typing import cast
from ipaddress import ip_address

from ..models.container import FullContainer, ContainerConfig
from ....utils.models import Container as ContainerRecord


def full_container_from_record(record: ContainerRecord) -> FullContainer:
    return FullContainer(
        ip              = ip_address(record.host.ip),
        mc_port         = cast(int, record.mc_port),
        rcon_port       = cast(int, record.rcon_port),
        config          = ContainerConfig.model_validate(record.config),
        subdomain       = cast(str, record.subdomain),
        to_be_deleted   = cast(bool, record.to_be_deleted),
        initialized     = cast(bool, record.initialized),
    )