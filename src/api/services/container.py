from ..data.models.host import HostConfig

from ..data.mappers.container import (
    full_container_from_record,
    user_full_container_from_record
)
from ..data.models.container import (
    ContainerConfig,
    ContainerData,
    FullContainer,
    OptContainerData,
    UserOptContainerData,
    OptContainerConfig,
    UserFullContainer
)

from ..data.models.validators import validate_container_ram_against_host
from ..data.models.response import MessageResponse
from ..data.models.utils import merge_configs

from ...utils.keygen import KeyGenerator

from ...exceptions.errors import BadRequestError, NotFoundError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ...gateway.server import Server



class ContainerService:
    """Utility class for executing API requests"""

    def __init__(self, *, server: 'Server') -> None:
        self.containers = server._sessions.containers
        self.hosts = server._sessions.containers.hosts
        self.server_sessions = server._sessions


    def add(self, data: ContainerData) -> FullContainer:

        host_records = self.hosts.storage.read(ip=str(data.ip))
        if not host_records:
            raise NotFoundError(f"host {data.ip} does not exist")
        host_cfg = HostConfig.model_validate(host_records[0].config)
        validate_container_ram_against_host(host_cfg, data.config)

        container = self.containers.create(
            str(data.ip),
            data.mc_port,
            data.rcon_port,
            data.config,
        )
        return full_container_from_record(container)


    def update(self, subdomain: str, data: OptContainerData | UserOptContainerData) -> FullContainer | UserFullContainer:

        data = ContainerService._convert_model(data)

        if not KeyGenerator.validate(subdomain):
            raise BadRequestError("subdomain is not valid")


        old_container_records = self.containers.storage.read(allow_empty=False, subdomain=subdomain)
        old_container = old_container_records[0]
        
        if old_container.host is None:
            raise NotFoundError(f"container has no host assigned")

        old_cfg = ContainerConfig.model_validate(old_container.config)
        new_cfg = merge_configs(old_cfg, data.config)

        self._validate_ram(
            str(data.ip) if data.ip else str(old_container.host.ip),
            new_cfg
        )

        container_updates = data.model_dump(exclude_unset=True, exclude_none=True)
        update_fields: dict = {
            **container_updates,
            "config": new_cfg.model_dump(mode="json")
        }

        if "ip" in update_fields:
            update_fields["host"] = str(update_fields.pop("ip"))

        update_fields["initialized"] = False

        updated_container = self.containers.storage.update(subdomain, **update_fields)
        if isinstance(data, UserOptContainerData):
            return user_full_container_from_record(updated_container)
        return full_container_from_record(updated_container)


    def remove(self, subdomain: str) -> FullContainer:
        records = self.containers.storage.read(allow_empty=False, subdomain=subdomain)
        deleted_container = records[0]

        self.server_sessions.interrupt(
            "Your server has been removed",
            subdomain=subdomain,
        )
        self.containers.delete(subdomain)
        return full_container_from_record(deleted_container)


    def kick(self, subdomain: str, username: str | None = None, message: str = "") -> MessageResponse:
        args = {"subdomain" : subdomain}
        if username is not None:
            args["username"] = username
        if message:
            args["reason"] = message

        self.server_sessions.interrupt(**args)

        if username is not None:
            return MessageResponse(message=f"Player {username} has been kicked from server {subdomain}")
        return MessageResponse(message=f"All players from server {subdomain} have been kicked")


    def read(self, subdomain: str | None = None, email: str | None = None) -> list[FullContainer] | list[UserFullContainer]:
        query = self.containers.storage.read(
            allow_empty=True,
            subdomain = subdomain,
            owner=email,
        )
        if email is not None:
            return [user_full_container_from_record(row) for row in query]
        return [full_container_from_record(row) for row in query]


    def assert_owner(self, subdomain: str, email: str) -> None:
        self.containers.storage.read(
            allow_empty=False,
            subdomain=subdomain,
            owner=email,
        )
        

    @staticmethod
    def _convert_model(user_config: OptContainerData | UserOptContainerData) -> OptContainerData:
        
        if isinstance(user_config, OptContainerData):
            return user_config

        config = OptContainerConfig.model_validate(
            user_config.model_dump(exclude_unset=True, exclude_none=True)
        )
        return OptContainerData(
            ip = None,
            mc_port = None,
            rcon_port = None,
            owner = None,
            config = config
        )


    def _validate_ram(self, ip, new_cfg):

        host_records = self.hosts.storage.read(ip=ip)
        if not host_records:
            raise NotFoundError(f"host {ip} does not exist")
        host_cfg = HostConfig.model_validate(host_records[0].config)
        validate_container_ram_against_host(host_cfg, new_cfg)
