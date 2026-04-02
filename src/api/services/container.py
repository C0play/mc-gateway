from ..data.models.host import HostConfig
from ..data.models.response import ListResponse, MessageResponse
from ..data.models.container import (
    ContainerConfig,
    ContainerData,
    FullContainer,
    OptContainerData,
    merge_configs
)
from ..data.models.validators import validate_container_ram_against_host

from ..data.mappers.container import full_container_from_record
from ...utils.composegen import PERFORMANCE_MODS
from ...utils.keygen import KeyGenerator

from ...exceptions.errors import BadRequestError, NotFoundError, UnauthorizedError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ...gateway.server import Server



class ContainerService:

    def __init__(self, *, server: 'Server') -> None:
        self.containers = server._sessions.containers
        self.hosts = server._sessions.containers.hosts
        self.server_sessions = server._sessions


    def container_add(self, data: ContainerData) -> FullContainer:
        for mod in PERFORMANCE_MODS:
            if mod not in data.config.modrinth_projects:
                data.config.modrinth_projects.append(mod)

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


    def container_update(self, subdomain: str, data: OptContainerData) -> FullContainer:
        if not KeyGenerator.validate(subdomain):
            raise BadRequestError("subdomain is not valid")

        old_container_records = self.containers.storage.read(subdomain=subdomain)
        if not old_container_records:
            raise NotFoundError(f"container {subdomain} does not exist")
        old_container = old_container_records[0]

        old_cfg = ContainerConfig.model_validate(old_container.config)
        new_cfg = merge_configs(old_cfg, data.config)

        for mod in PERFORMANCE_MODS:
            if mod not in new_cfg.modrinth_projects:
                new_cfg.modrinth_projects.append(mod)

        target_ip = str(data.ip) if data.ip else str(old_container.host.ip)
        host_records = self.hosts.storage.read(ip=target_ip)
        if not host_records:
            raise NotFoundError(f"host {target_ip} does not exist")
        host_cfg = HostConfig.model_validate(host_records[0].config)
        validate_container_ram_against_host(host_cfg, new_cfg)

        container_updates = data.model_dump(exclude_unset=True, exclude_none=True)
        update_fields: dict = {**container_updates, "config": new_cfg.model_dump(mode="json")}

        if "ip" in update_fields:
            update_fields["host"] = str(update_fields.pop("ip"))

        update_fields["initialized"] = False

        updated_container = self.containers.storage.update(subdomain, **update_fields)
        return full_container_from_record(updated_container)


    def container_remove(self, subdomain: str) -> FullContainer:
        records = self.containers.storage.read(subdomain=subdomain)
        if not records:
            raise NotFoundError(f"container {subdomain} does not exist")
        deleted_container = records[0]

        self.server_sessions.interrupt(
            "Your server has been removed",
            subdomain=subdomain,
        )
        self.containers.delete(subdomain)
        return full_container_from_record(deleted_container)


    def container_kick(self, subdomain: str) -> MessageResponse:
        self.server_sessions.interrupt(subdomain=subdomain)
        return MessageResponse(message=f"All players from server {subdomain} have been kicked")


    def container_get(self, 
            subdomain: str | None = None,
            owner_email: str | None = None
        ) -> ListResponse:
        query = self.containers.storage.read(
            ubdomain = subdomain,
            owner=owner_email,
        )
        lst = [full_container_from_record(row) for row in query]
        return ListResponse(root=lst)
    

    def validate_owner(self, subdomain: str, owner_email: str) -> None:
        records = self.containers.storage.read(
            subdomain=subdomain,
            owner=owner_email,
        )
        if not records:
            raise UnauthorizedError("you are no the owner")
        