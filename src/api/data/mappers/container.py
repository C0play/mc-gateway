from typing import cast
from ipaddress import ip_address

from ..models.container import FullContainer, ContainerConfig, UserFullContainer, UserContainerConfig
from ....utils.models import Container as ContainerRecord


def full_container_from_record(record: ContainerRecord) -> FullContainer:
    """Maps a container record to it's full pydantic model."""
    return FullContainer(
        ip              = ip_address(record.host.ip),
        mc_port         = cast(int, record.mc_port),
        rcon_port       = cast(int, record.rcon_port),
        config          = ContainerConfig.model_validate(record.config),
        owner           = str(record.owner), 
        subdomain       = str(record.subdomain),
        to_be_deleted   = cast(bool, record.to_be_deleted),
        initialized     = cast(bool, record.initialized),
    )

def user_full_container_from_record(record: ContainerRecord) -> UserFullContainer:
    """Maps a container record to it's stripped pydantic model for users."""
    return UserFullContainer(
        config          = UserContainerConfig.model_validate(record.config),
        subdomain       = str(record.subdomain),
        initialized     = cast(bool, record.initialized)
    )