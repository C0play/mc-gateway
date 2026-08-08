from typing import Any

import yaml

from ..api.data.models.container import ContainerConfig
from ..api.data.models.host import HostConfig
from ..container.repository import BaseContainerRepository
from ..host.repository import BaseHostRepository


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
            NorFoundError: If the container doesn't exist.
        """

        container_record = self.containers.read(allow_empty=False, subdomain=subdomain)[0]
        host_record = self.hosts.read(ip=container_record.host)[0]

        compose_cfg = ContainerConfig.model_validate(container_record.config)
        host_cfg = HostConfig.model_validate(host_record.config)


        container_ram_val = ComposeGenerator.to_Mb(compose_cfg.ram)
        init_ram_val = ComposeGenerator.to_Mb(host_cfg.init_memory)
        max_ram_val = ComposeGenerator.to_Mb(host_cfg.max_memory)
        if not (init_ram_val <= container_ram_val <= max_ram_val):
            raise ValueError("container memory is not within [init_memory, max_memory] range.")

        custom_server_properties = ["LOG_IPS=true"]

        environment = {
            "UID": host_cfg.uid,
            "GID": host_cfg.gid,
            "RCON_PASSWORD": rcon_password,
            "EULA": "TRUE",
            "TYPE": "FABRIC", # Default to Fabric for performance mods support
            "INIT_MEMORY": host_cfg.init_memory,
            "MAX_MEMORY": host_cfg.max_memory,
            "TZ": str(host_cfg.timezone),
            "VIEW_DISTANCE": str(compose_cfg.view_distance),
            "VERSION": compose_cfg.version,
            "MODRINTH_ALLOWED_VERSION_TYPE": compose_cfg.mod_version_type,
            "PAUSE_WHEN_EMPTY_SECONDS": "300",
            "PLAYER_IDLE_TIMEOUT": "10",
            "ENABLE_ROLLING_LOGS": "true",
            "LOG_TIMESTAMP": "true",
        }

        environment["MODRINTH_PROJECTS"] = ",".join(compose_cfg.modrinth_projects)
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
