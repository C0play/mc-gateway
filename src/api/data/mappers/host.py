from ipaddress import ip_address

from pydantic_extra_types.mac_address import MacAddress

from ....utils.models import Host
from ..models.host import FullHost, HostConfig


def full_host_from_record(record: Host) -> FullHost:
    """Maps a host record to it's pydantic model."""
    return FullHost(
        ip=ip_address(str(record.ip)),
        mac=MacAddress(record.mac),
        config=HostConfig.model_validate(record.config),
    )
