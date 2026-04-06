from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    IPvAnyAddress
)
from pydantic_extra_types.mac_address import MacAddress
from pydantic_extra_types.timezone_name import TimeZoneName
from .validators import (
    validate_linux_user,
    validate_absolute_path,
    check_path_user_consistency,
    validate_init_min_max_consistency
)


class HostConfig(BaseModel):
    """
    Host-specific config injected into compose.yml.
    Stored as JSON in the Host.config column.
    Every field has a default in the compose file, so an empty JSON object is valid.
    """

    user: str = Field(..., max_length=50, description="User of the host machine")
    path: str = Field(..., description="Path to the directory containing all minecraft server directories")
    uid: int = Field(..., ge=1000, le=59999, description="UID for the container process")
    gid: int = Field(..., ge=1000, le=59999, description="GID for the container process")
    timezone: TimeZoneName = Field(..., description="Container timezone")
    init_memory: str = Field(..., description="Initial JVM heap size")
    max_memory: str = Field(..., description="Maximum ram amount a server can use")
    cpu_count: int = Field(..., ge=1, description="Number of CPU cores for the container")


    @field_validator("user")
    @classmethod
    def validate_user(cls, v: str) -> str:
        return validate_linux_user(v)

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return validate_absolute_path(v)

    @model_validator(mode="after")
    def validate_ram_alloc(self: 'HostConfig') -> 'HostConfig':
        validate_init_min_max_consistency(
            self.init_memory,
            self.max_memory
        )
        return self
    
    @model_validator(mode='after')
    def validate_path_user_consistency(self) -> 'HostConfig':
        check_path_user_consistency(self.user, self.path)
        return self


class OptHostConfig(BaseModel):
    """Partial host config for updates."""

    user: str | None = Field(None, max_length=50, description="User of the host machine")
    path: str | None = Field(None, description="Path to the directory containing all minecraft server directories")
    uid: int | None = Field(None, ge=1000, le=59999, description="UID for the container process")
    gid: int | None = Field(None, ge=1000, le=59999, description="GID for the container process")
    timezone: TimeZoneName | None = Field(None, description="Container timezone")
    init_memory: str | None = Field(None, description="Initial JVM heap size")
    max_memory: str | None = Field(None, description="maximum ram amount a server can use")
    cpu_count: int | None = Field(None, ge=1, description="Number of CPU cores for the container")


    @field_validator("user")
    @classmethod
    def validate_user(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_linux_user(v)
        return v

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_absolute_path(v)
        return v

    @model_validator(mode="after")
    def validate_ram_alloc(self: 'OptHostConfig') -> 'OptHostConfig':
        validate_init_min_max_consistency(
            self.init_memory,
            self.max_memory
        )
        return self

    @model_validator(mode='after')
    def validate_path_user_consistency(self) -> 'OptHostConfig':
        check_path_user_consistency(self.user, self.path)
        return self



class HostID(BaseModel):
    ip: IPvAnyAddress = Field(..., description="IP address of the host machine")


class HostData(BaseModel):
    """Host parameters."""
    mac: MacAddress = Field(..., description="MAC address of the host machine")
    config: HostConfig = Field(..., description="Host-specific compose.yml config")


class OptHostData(BaseModel):
    """Host parameters for updating."""
    mac: MacAddress | None = Field(None, description="MAC address of the host machine")
    config: OptHostConfig | None = Field(None, description="Partial host-specific compose.yml config (merged with existing)")


class FullHost(HostID, HostData):
    """Host model equivalent to a DB record."""
    pass
