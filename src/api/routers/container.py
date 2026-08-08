from typing import Annotated
from fastapi import APIRouter, Security

from ..data.models.container import (
    ContainerData,
    OptContainerData,
    UserOptContainerData,
    FullContainer,
    UserFullContainer,
)
from ..data.models.response import MessageResponse
from ..services.container import ContainerService
from ..security import Permission, AuthorizationManager, AuthContext



class ContainerRouter:
    """Defines API endpoints used for container management."""

    def __init__(self, container_service: ContainerService, auth: AuthorizationManager) -> None:
        self.containers = container_service
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/containers", tags=["containers"])
        REQ = self.auth.require

        @router.post(
            "/",
            dependencies = [Security(REQ, scopes=[Permission.container_create])],
            response_model = FullContainer
        )
        def create_container(data: ContainerData):
            return self.containers.add(data)

        @router.get("/", response_model = list[FullContainer] | list[UserFullContainer])
        def fetch_container(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.container_read])],
            subdomain: str | None = None,
        ):
            if auth.user_role.requires_ownership:
                return self.containers.read(subdomain, auth.user_email)
            
            return self.containers.read(subdomain)


        @router.patch(
            "/{subdomain}",
            response_model = FullContainer | UserFullContainer
        )
        def update_container(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.container_update])],
            subdomain: str,
            data: OptContainerData | UserOptContainerData,
        ):
            if auth.user_role.requires_ownership:
                self.containers.assert_owner(subdomain, auth.user_email)

            return self.containers.update(subdomain, data)


        @router.delete(
            "/{subdomain}",
            dependencies = [Security(REQ, scopes=[Permission.container_delete])],
            response_model = FullContainer
        )
        def remove_container(subdomain: str):
            return self.containers.remove(subdomain)


        @router.post(
            "/{subdomain}/kick",
            response_model = MessageResponse
        )
        def kick_all_from_container(
            auth: Annotated[AuthContext, Security(REQ, scopes=[Permission.container_kick])],
            subdomain: str,
        ):
            if auth.user_role.requires_ownership:
                 self.containers.assert_owner(subdomain, auth.user_email)
                 
            return self.containers.kick(subdomain)


        return router