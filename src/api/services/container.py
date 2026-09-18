from typing import TYPE_CHECKING

from ...exceptions.errors import BadRequestError
from ...utils.keygen import KeyGenerator
from ..data.mappers.container import (
    full_container_from_record,
)
from ..data.models.container import (
    ContainerConfig,
    ContainerData,
    FullContainer,
    OptContainerData,
)
from ..data.models.response import MessageResponse
from ..data.models.utils import merge_configs

if TYPE_CHECKING:
    from ...gateway.server import Server


class ContainerService:
    """Utility class for executing API requests"""

    def __init__(self, server: "Server") -> None:
        self.containers = server._sessions.containers
        self.hosts = server._sessions.containers.hosts
        self.server_sessions = server._sessions

    def add(self, data: ContainerData) -> FullContainer:

        container = self.containers.create(str(data.ip), data.config)
        return full_container_from_record(container)

    def update(self, subdomain: str, data: OptContainerData) -> FullContainer:

        if not KeyGenerator.validate(subdomain):
            raise BadRequestError("subdomain is not valid")

        old_container_records = self.containers.storage.read(
            allow_empty=False, subdomain=subdomain
        )
        old_container = old_container_records[0]

        old_cfg = ContainerConfig.model_validate(old_container.config)
        new_cfg = merge_configs(old_cfg, data.config)

        container_updates = data.model_dump(exclude_unset=True, exclude_none=True)
        update_fields: dict = {
            **container_updates,
            "config": new_cfg.model_dump(mode="json"),
        }

        if "ip" in update_fields:
            update_fields["host"] = str(update_fields.pop("ip"))

        update_fields["initialized"] = False

        updated_container = self.containers.storage.update(subdomain, **update_fields)
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

    def kick(
        self, subdomain: str, username: str = "", message: str = "",
    ) -> MessageResponse:
        args = {"subdomain": subdomain}
        if username:
            args["username"] = username
        if message:
            args["reason"] = message

        self.server_sessions.interrupt(**args)

        if username:
            return MessageResponse(
                message=f"Player {username} has been kicked from server {subdomain}"
            )
        return MessageResponse(
            message=f"All players from server {subdomain} have been kicked"
        )

    def read(
        self, subdomain: str | None = None, email: str | None = None
    ) -> list[FullContainer]:
        query = self.containers.storage.read(
            allow_empty=True,
            subdomain=subdomain,
            owner=email,
        )
        return [full_container_from_record(row) for row in query]
