from typing import (
    Literal,
    TypeAlias
)
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    IPvAnyAddress
)
from ..utils.validators import validate_subdomain



Difficulty: TypeAlias = Literal["peaceful", "easy", "normal", "hard"]
ReleaseType: TypeAlias = Literal["release", "beta", "alpha"]

class ContainerConfig(BaseModel):
    """
    Configuration model for generating compose.yml files.
    """

    ram: str = Field("2G", description="The amount of memory to allocate (e.g., '2G', '4G')")
    version: str = Field("LATEST", description="The Minecraft version to use")
    view_distance: int = Field(10, ge=1, le=32, description="Server view distance")
    mod_version_type: ReleaseType = Field("release", description="Allowed mod release type for Modrinth projects")
    modrinth_projects: list[str] = Field(default_factory=list, description="List of Modrinth mods URLs or IDs to install")


class OptComposeConfig(BaseModel):
    """
    Configuration model for generating compose.yml files.
    """

    ram: str | None = Field(None, description="The amount of memory to allocate (e.g., '2G', '4G')")
    version: str | None = Field(None, description="The Minecraft version to use")
    view_distance: int | None = Field(None, ge=1, le=32, description="Server view distance")
    mod_version_type: ReleaseType | None = Field(None, description="Allowed mod release type for Modrinth projects")
    modrinth_projects: list[str] | None = Field(None, description="List of Modrinth mods URLs or IDs to install")



# ======================================== CONTAINER MODELS ========================================

class ContainerID(BaseModel):
    subdomain: str = Field(..., min_length=4, max_length=4, description="Subdomain assigned to the container")

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        return validate_subdomain(v)


class ContainerData(BaseModel):
    ip: IPvAnyAddress = Field(..., description="IP address of the host machine assigned to the container")
    mc_port: int = Field(..., description="Minecraft port of the host machine assigned to the container")
    rcon_port: int = Field(..., description="RCON port of the host machine assigned to the container")
    config: ContainerConfig = Field(..., description="YAML file variables to use for server confguration")


class OptContainerData(BaseModel):
    ip: IPvAnyAddress | None = Field(None, description="IP address of the host machine assigned to the container")
    mc_port: int | None = Field(None, description="Minecraft port of the host machine assigned to the container")
    rcon_port: int | None = Field(None, description="RCON port of the host machine assigned to the container")
    config: OptComposeConfig | None = Field(None, description="Partial YAML config merged with current container settings")


class FullContainer(ContainerID, ContainerData):
    initialized: bool = Field(..., description="Flag whether compose.yml was deployed on the host")
    to_be_deleted: bool = Field(..., description="Flag whether container is set to be deleted")
