from fastapi import APIRouter, Security

from ..data.models.container import (
    ContainerData,
    FullContainer,
    OptContainerData,
)
from ..data.models.response import MessageResponse
from ..security import AuthorizationManager, Permission
from ..services.container import ContainerService


class ContainerRouter:
    """Defines API endpoints used for container management."""

    def __init__(self, container_service: ContainerService, auth: AuthorizationManager):
        self.containers = container_service
        self.auth = auth

    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/containers", tags=["containers"])
        REQ = self.auth.require

        @router.post(
            "/",
            dependencies=[Security(REQ, scopes=[Permission.container_create])],
            response_model=FullContainer,
        )
        def create_container(data: ContainerData):
            return self.containers.add(data)

        @router.get(
            "/",
            dependencies=[Security(REQ, scopes=[Permission.container_read])],
            response_model=list[FullContainer],
        )
        def fetch_container(subdomain: str | None = None):
            return self.containers.read(subdomain)

        @router.patch(
            "/{subdomain}",
            dependencies=[Security(REQ, scopes=[Permission.container_update])],
            response_model=FullContainer,
        )
        def update_container(subdomain: str, data: OptContainerData):
            return self.containers.update(subdomain, data)

        @router.delete(
            "/{subdomain}",
            dependencies=[Security(REQ, scopes=[Permission.container_delete])],
            response_model=FullContainer,
        )
        def remove_container(subdomain: str):
            return self.containers.remove(subdomain)

        @router.post(
            "/{subdomain}/kick",
            dependencies=[Security(REQ, scopes=[Permission.container_kick])],
            response_model=MessageResponse,
        )
        def kick_from_container(subdomain: str, username: str = "", message: str = ""):
            return self.containers.kick(subdomain, username, message)

        return router
