from typing import (
    Any,
    Literal,
    TypeAlias
)

import yaml
from pydantic import (
    BaseModel,
    Field,
    field_validator
)

from .validators import validate_ram_allocation


Difficulty: TypeAlias = Literal["peaceful", "easy", "normal", "hard"]
ReleaseType: TypeAlias = Literal["release", "beta", "alpha"]

class ComposeConfig(BaseModel):
    """
    Configuration model for generating docker-compose.yml files.
    """
    ram: str = Field("2G", description="The amount of memory to allocate (e.g., '2G', '4G')")
    version: str = Field("LATEST", description="The Minecraft version to use")
    difficulty: Difficulty = Field("easy", description="Game difficulty (peaceful, easy, normal, hard)")
    view_distance: int = Field(10, ge=1, le=32, description="Server view distance")
    mod_version_type: ReleaseType = Field("release", description="Allowed mod release type for Modrinth projects")
    modrinth_projects: list[str] = Field(default_factory=list, description="List of Modrinth mods URLs or IDs to install")

    @field_validator("ram")
    @classmethod
    def validate_ram(cls, v: str) -> str:
        return validate_ram_allocation(v)

class OptComposeConfig(BaseModel):
    """
    Configuration model for generating docker-compose.yml files.
    """
    ram: str | None = Field(None, description="The amount of memory to allocate (e.g., '2G', '4G')")
    version: str | None = Field(None, description="The Minecraft version to use")
    difficulty: Difficulty | None = Field(None, description="Game difficulty (peaceful, easy, normal, hard)")
    view_distance: int | None = Field(None, ge=1, le=32, description="Server view distance")
    mod_version_type: ReleaseType | None = Field(None, description="Allowed mod release type for Modrinth projects")
    modrinth_projects: list[str] | None = Field(None, description="List of Modrinth mods URLs or IDs to install")

    @field_validator("ram")
    @classmethod
    def validate_ram(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_ram_allocation(v)
        return v


def generate_compose(mc_port: int, rcon_port: int, rcon_password: str, config: ComposeConfig) -> str:
    """
    Generates a compose.yml file for a Minecraft server.

    Args:
        mc_port: External docker port for the Minecraft server.
        rcon_port: External docker port for RCON.
        rcon_password: The RCON password for the server.
        config: The configuration object containing generation parameters.

    Returns:
        str: The YAML content as a string.
    """

    # Default optimization mods for Fabric
    performance_mods = [
        "fabric-api:0.133.4+1.21.8",
        "lithium:mc1.21.8-0.18.1-fabric",
        "sodium:mc1.21.8-0.7.0-fabric",
        "c2me-fabric:0.3.4.0.0+1.21.8",
        "ferrite-core:8.0.0-fabric",
    ]

    final_mods = config.modrinth_projects.copy()
    for pm in performance_mods:
        if pm not in final_mods:
            final_mods.append(pm)
    
    custom_server_properties = ["LOG_IPS=true"]

    environment = {
        "UID": 1001,
        "GID": 1001,
        "RCON_PASSWORD": rcon_password,
        "EULA": "TRUE",
        "TYPE": "FABRIC", # Default to Fabric for performance mods support
        "INIT_MEMORY": "1024M",
        "MAX_MEMORY": config.ram,
        "TZ": "Europe/Warsaw",
        "DIFFICULTY": config.difficulty,
        "FORCE_GAMEMODE": "true",
        "VIEW_DISTANCE": str(config.view_distance),
        "VERSION": config.version,
        "MODRINTH_ALLOWED_VERSION_TYPE": config.mod_version_type,
        "PAUSE_WHEN_EMPTY_SECONDS": "300",
        "PLAYER_IDLE_TIMEOUT": "10",
        "ENABLE_ROLLING_LOGS": "true",
        "LOG_TIMESTAMP": "true",
    }

    environment["MODRINTH_PROJECTS"] = ",".join(final_mods)
    environment["CUSTOM_SERVER_PROPERTIES"] = ",".join(custom_server_properties)
    
    compose_content: dict[str, Any] = {
        "services": {
            "mc": {
                "image": "itzg/minecraft-server:latest",
                "container_name": f"mc_{mc_port}",
                "cpu_count": 2,
                "tty": True,
                "stdin_open": True,
                "stop_grace_period": "60s",
                "ports": [
                f"{mc_port}:25565",
                f"{rcon_port}:25575",
                ],
                "environment": environment,
                "volumes": [
                    "./data:/data"
                ],
            }
        }
    }
    
    return yaml.dump(
        compose_content, 
        default_flow_style=False, 
        sort_keys=False
    )
