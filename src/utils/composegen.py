import yaml
from typing import Any

from ..host.repository import BaseHostRepository
from ..host.models import HostConfig
from ..container.repository import BaseContainerRepository
from ..container.models import ContainerConfig



# Default optimization mods for Fabric 1.21.8
PERFORMANCE_MODS = [
        "fabric-api:0.133.4+1.21.8",
        "lithium:mc1.21.8-0.18.1-fabric",
        "sodium:mc1.21.8-0.7.0-fabric",
        "c2me-fabric:0.3.4.0.0+1.21.8",
        "ferrite-core:8.0.0-fabric",
    ]


class ComposeGenerator:

    def __init__(self, host_repo: BaseHostRepository, container_repo: BaseContainerRepository) -> None:
        self.hosts = host_repo
        self.containers = container_repo


    def generate(self, subdomain: str, rcon_password: str) -> str:
        """
        Generates a compose.yml file for a Minecraft server.

        Returns:
            str: The YAML content as a string.

        Raises:
            ValueError: If an argument fails validation.
        """

        container_record = self.containers.read(subdomain=subdomain)[0]
        host_record = self.hosts.read(ip=container_record.host)[0]

        compose_cfg = ContainerConfig.model_validate(container_record.config)
        host_cfg = HostConfig.model_validate(host_record.config)


        container_ram_val = ComposeGenerator.to_Mb(compose_cfg.ram)
        init_ram_val = ComposeGenerator.to_Mb(host_cfg.init_memory)
        max_ram_val = ComposeGenerator.to_Mb(host_cfg.max_memory)
        if not (init_ram_val <= container_ram_val and container_ram_val <= max_ram_val):
            raise ValueError(f"container memory is not within [init_memory, max_memory] range.")

        final_mods = compose_cfg.modrinth_projects.copy()
        for pm in PERFORMANCE_MODS:
            if pm not in final_mods:
                final_mods.append(pm)
        
        custom_server_properties = ["LOG_IPS=true"]

        environment = {
            "UID": host_cfg.uid,
            "GID": host_cfg.gid,
            "RCON_PASSWORD": rcon_password,
            "EULA": "TRUE",
            "TYPE": "FABRIC", # Default to Fabric for performance mods support
            "INIT_MEMORY": host_cfg.init_memory,
            "MAX_MEMORY": host_cfg.max_memory,
            "TZ": host_cfg.timezone,
            "VIEW_DISTANCE": str(compose_cfg.view_distance),
            "VERSION": compose_cfg.version,
            "MODRINTH_ALLOWED_VERSION_TYPE": compose_cfg.mod_version_type,
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
                    "container_name": f"mc_{container_record.mc_port}",
                    "cpu_count": host_cfg.cpu_count,
                    "tty": True,
                    "stdin_open": True,
                    "stop_grace_period": "60s",
                    "ports": [
                    f"{container_record.mc_port}:25565",
                    f"{container_record.rcon_port}:25575",
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
    

    @staticmethod
    def to_Mb(ram: str) -> int:
        return int(ram[:-1]) * (1024 if ram[-1] == "G" else 1)