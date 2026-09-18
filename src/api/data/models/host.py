from pydantic import BaseModel, Field, IPvAnyAddress
from pydantic_extra_types.mac_address import MacAddress


class HostConfig(BaseModel):
    authority: str = Field(
        description="mc-gateway-controller server authority (<proto>://<authority>/<path>)"
    )


class OptHostConfig(BaseModel):
    authority: str | None = Field(
        None,
        description="mc-gateway-controller server authority (<proto>://<authority>/<path>)",
    )


class HostID(BaseModel):
    ip: IPvAnyAddress = Field(..., description="IP address of the host machine")


class HostData(BaseModel):
    """Host parameters."""

    mac: MacAddress = Field(..., description="MAC address of the host machine")
    config: HostConfig = Field(..., description="Host-specific compose.yml config")


class OptHostData(BaseModel):
    """Host parameters for updating."""

    mac: MacAddress | None = Field(None, description="MAC address of the host machine")
    config: OptHostConfig | None = Field(
        None,
        description="Partial host-specific compose.yml config (merged with existing)",
    )


class FullHost(HostID, HostData):
    """Host model equivalent to a DB record."""
