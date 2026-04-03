from typing import Annotated

from fastapi import APIRouter, Depends

from ..data.models.container import (
    ContainerData,
    OptContainerData,
    UserOptContainerData,
    FullContainer
)

from ..data.models.response import ListResponse, MessageResponse
from ..services.container import ContainerService
from .utils import handle_errors
from ..security import Permission, AuthorizationManager, AuthContext
from ...exceptions import ForbiddenError



class ContainerRouter:

    def __init__(self, container_service: ContainerService, auth: AuthorizationManager) -> None:
        self.containers = container_service
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/container", tags=["containers"])

        MANAGE_ALL = self.auth.require(Permission.container_manage_all)
        MANAGE_ANY = self.auth.require_any(
            Permission.container_manage_all,
            Permission.container_manage_own
        )

        @router.post(
            "/add",
            dependencies = [Depends(MANAGE_ALL)],
            response_model = FullContainer
        )
        @handle_errors
        def create_container(data: ContainerData):
            return self.containers.add(data)


        @router.delete(
            "/remove/{subdomain}",
            dependencies = [Depends(MANAGE_ALL)],
            response_model = FullContainer
        )
        @handle_errors
        def remove_container(subdomain: str):
            return self.containers.remove(subdomain)
        

        @router.put(
            "/update/{subdomain}",
            response_model = FullContainer
        )
        @handle_errors
        def update_container(
            subdomain: str,
            data: OptContainerData | UserOptContainerData,
            auth_context: Annotated[AuthContext, Depends(MANAGE_ANY)],
        ):
            if not self._is_admin(auth_context):
                self.containers.assert_owner(subdomain, auth_context.user_email)

            return self.containers.update(subdomain, data)


        @router.get(
            "/list",
            response_model = ListResponse
        )
        @handle_errors
        def fetch_container(
            auth_context: Annotated[AuthContext, Depends(MANAGE_ANY)],
            subdomain: str | None = None,
        ):
            if not self._is_admin(auth_context):
                if subdomain is None:
                    raise ForbiddenError("you not permitted to view all containers")
                self.containers.assert_owner(subdomain, auth_context.user_email)
                
                return self.containers.read(subdomain, auth_context.user_email)
            
            return self.containers.read(subdomain)
            

        @router.post(
            "/kick/{subdomain}",
            response_model = MessageResponse
        )
        @handle_errors
        def kick_all_from_container(
            subdomain: str,
            auth_context: Annotated[AuthContext, Depends(MANAGE_ANY)]
        ):
            if not self._is_admin(auth_context):
                 self.containers.assert_owner(subdomain, auth_context.user_email)
                 
            return self.containers.kick(subdomain)


        return router


    # =================================== HELPERS ===================================

    def _is_admin(self, auth_context: AuthContext) -> bool:
        return self.auth.roles.validate(Permission.container_manage_all, auth_context.user_role)