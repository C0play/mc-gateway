from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator, model_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from .validators import validate_init_min_max_consistency, validate_subdomain

Difficulty: TypeAlias = Literal["peaceful", "easy", "normal", "hard"]
ReleaseType: TypeAlias = Literal["release", "beta", "alpha"]


class ContainerConfig(BaseModel):
    # Environment
    uid: int = Field(1000, description="User id to run the container as.")
    gid: int = Field(1000, description="Group id to run the container as.")
    timezone: TimeZoneName = Field(..., description="Container timezone.")
    # Resources
    init_memory: str = Field(
        "2G",
        description="The amount of memory to allocate on start (e.g., '2G', '4G').",
    )
    max_memory: str = Field(
        "2G", description="The maximum amount of memory to allocate (e.g., '2G', '4G')."
    )
    cpu_count: int = Field(..., description="Number of CPU cores for the container.")
    # Ports
    mc_port: int = Field(..., description="Port used for minecraft client connections.")
    rcon_port: int = Field(..., description="Port used for RCON connections.")
    # Minecraft
    type: str = Field("FABRIC", description="Server type (e.g. FABRIC, VANILLA, ...)")
    version: str = Field("LATEST", description="Minecraft version to use.")
    view_distance: int = Field(10, ge=1, le=32, description="Server view distance.")
    mod_version_type: ReleaseType = Field(
        "release", description="Allowed mod release type for Modrinth projects."
    )
    modrinth_projects: list[str] = Field(
        [],
        description="List of Modrinth mod URLs or IDs to install.",
    )
    rcon_password: str = Field(description="RCON password used by the gateway.")
    # Server
    custom_server_properties: list = Field([], description="List of custom properties.")

    @model_validator(mode="after")
    def validate_ram_alloc(self: "ContainerConfig") -> "ContainerConfig":
        validate_init_min_max_consistency(self.init_memory, self.max_memory)
        return self


class OptContainerConfig(BaseModel):
    """Configuration model for updating compose.yml files."""

    # Environment
    uid: int | None = Field(None, description="User id to run the container as.")
    gid: int | None = Field(None, description="Group id to run the container as.")
    timezone: TimeZoneName | None = Field(None, description="Container timezone.")
    # Resources
    init_memory: str | None = Field(
        None,
        description="The amount of memory to allocate on start (e.g., '2G', '4G').",
    )
    max_memory: str | None = Field(
        None,
        description="The maximum amount of memory to allocate (e.g., '2G', '4G').",
    )
    cpu_count: int | None = Field(
        None, description="Number of CPU cores for the container."
    )
    # Ports
    mc_port: int | None = Field(
        None, description="Port used for minecraft client connections."
    )
    rcon_port: int | None = Field(None, description="Port used for RCON connections.")
    # Minecraft
    type: str | None = Field(
        None, description="Server type (e.g. FABRIC, VANILLA, ...)"
    )
    version: str | None = Field(None, description="Minecraft version to use.")
    view_distance: int | None = Field(
        None, ge=1, le=32, description="Server view distance."
    )
    mod_version_type: ReleaseType | None = Field(
        None, description="Allowed mod release type for Modrinth projects."
    )
    modrinth_projects: list[str] | None = Field(
        None,
        description="List of Modrinth mod URLs or IDs to install.",
    )
    rcon_password: str | None = Field(
        None, description="RCON password used by the gateway."
    )
    # Server
    custom_server_properties: list | None = Field(
        None, description="List of custom properties."
    )


class _ContainerID(BaseModel):
    subdomain: str = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Subdomain assigned to the container",
    )

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        return validate_subdomain(v)


class ContainerData(BaseModel):
    """Container model equivalent to a DB record without deployment flags."""

    ip: IPvAnyAddress = Field(
        ..., description="IP address of the host machine assigned to the container"
    )
    owner: str = Field(..., description="Email address of the container owner")
    config: ContainerConfig = Field(
        ..., description="YAML file variables to use for server configuration"
    )


class OptContainerData(BaseModel):
    """Container model for updating a DB record."""

    ip: IPvAnyAddress | None = Field(
        None, description="IP address of the host machine assigned to the container"
    )
    owner: str | None = Field(None, description="Email address of the container owner")
    config: OptContainerConfig | None = Field(
        None, description="Partial YAML config merged with current container settings"
    )


class FullContainer(_ContainerID, ContainerData):
    """Container model equivalent to a DB record."""

    initialized: bool = Field(
        ..., description="Flag whether compose.yml was deployed on the host"
    )
    to_be_deleted: bool = Field(
        ..., description="Flag whether container is set to be deleted"
    )
