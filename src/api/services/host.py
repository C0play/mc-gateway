from ..data.mappers.host import full_host_from_record
from ..data.models.host import FullHost, HostConfig, OptHostData
from ..data.models.container import merge_configs
from ..data.models.response import ListResponse, MessageResponse
from ...exceptions.errors import NotFoundError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ...gateway.server import Server



class HostService:

    def __init__(self, *,server: 'Server') -> None:
        self.hosts = server._sessions.containers.hosts
        self.server_sessions = server._sessions

    
    def host_add(self, host: FullHost) -> FullHost:
        config_json = host.config.model_dump(mode="json")
        new_host = self.hosts.storage.create(
            str(host.ip),
            str(host.mac),
            config_json,
        )
        return full_host_from_record(new_host)

    
    def host_update(self, ip: str, data: OptHostData) -> FullHost:
        updates = data.model_dump(exclude_unset=True, exclude_none=True)

        if data.config is not None:
            curr_records = self.hosts.storage.read(ip=ip)
            if not curr_records:
                raise NotFoundError(f"host {ip} does not exist")
            curr_cfg = HostConfig.model_validate(curr_records[0].config)
            new_cfg = merge_configs(curr_cfg, data.config)
            updates["config"] = new_cfg.model_dump(mode="json")

        new_host = self.hosts.storage.update(ip, **updates)
        return full_host_from_record(new_host)

    
    def host_remove(self, ip: str) -> FullHost:
        records = self.hosts.storage.read(ip=ip)
        if not records:
            raise NotFoundError(f"host {ip} does not exist")
        deleted_host = records[0]

        self.server_sessions.interrupt(
            "Your server has been removed",
            ip=ip,
        )
        self.hosts.delete(ip)
        return full_host_from_record(deleted_host)

    
    def host_kick(self, ip: str) -> MessageResponse:
        self.server_sessions.interrupt(ip=ip)
        return MessageResponse(
            message=f"All players from {ip} have been kicked"
        )

    
    def host_list(self, ip: str | None = None) -> ListResponse:
        query = self.hosts.storage.read(ip=ip)
        lst = [full_host_from_record(row) for row in query]
        return ListResponse(root=lst)