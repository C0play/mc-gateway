from typing import Annotated

from fastapi import APIRouter, Depends

from ..data.models.container import (
    ContainerData,
    OptContainerData,
    OptContainerConfig,
    UserOptContainerData,
    FullContainer
)

from ..data.models.response import ListResponse, MessageResponse
from ..services.container import ContainerService
from .utils import handle_errors
from ..security import Permission, AuthorizationManager, AuthContext



class ContainerRouter:

    def __init__(self, container_service: ContainerService, auth: AuthorizationManager) -> None:
        self.container_service = container_service
        self.auth = auth


    def get_router(self) -> APIRouter:

        router = APIRouter(prefix="/container")

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
        def container_add(data: ContainerData):
            return self.container_service.container_add(data)


        @router.delete(
            "/remove/{subdomain}",
            dependencies = [Depends(MANAGE_ALL)],
            response_model = FullContainer
        )
        @handle_errors
        def container_remove(subdomain: str):
            return self.container_service.container_remove(subdomain)
        

        @router.put(
            "/update/{subdomain}",
            response_model = FullContainer
        )
        @handle_errors
        def container_update(
            subdomain: str,
            data: OptContainerData | UserOptContainerData,
            auth_context: Annotated[AuthContext, Depends(MANAGE_ANY)],
        ):
            data = ContainerRouter._generate_update_data(data)
            
            if not self._is_admin(auth_context):
                self.container_service.validate_owner(subdomain, auth_context.user_email)

            return self.container_service.container_update(subdomain, data)


        @router.get(
            "/list",
            response_model = ListResponse
        )
        @handle_errors
        def container_get(
            auth_context: Annotated[AuthContext, Depends(MANAGE_ANY)],
            subdomain: str | None = None,
        ):
            if not self._is_admin(auth_context):
                self.container_service.validate_owner(subdomain, auth_context.user_email)
                return self.container_service.container_get(subdomain, auth_context.user_email)
            
            return self.container_service.container_get(subdomain)
            


        @router.post(
            "/kick/{subdomain}",
            response_model = MessageResponse
        )
        @handle_errors
        def container_kick(
            subdomain: str,
            auth_context: Annotated[AuthContext, Depends(MANAGE_ANY)]
        ):
            if not self._is_admin(auth_context):
                 self.container_service.validate_owner(subdomain, auth_context.user_email)
            return self.container_service.container_kick(subdomain)


        return router


    # =================================== HELPERS ===================================

    def _is_admin(self, auth_context: AuthContext) -> bool:
        return self.auth.roles.validate(Permission.container_manage_all, auth_context.user_role)


    @staticmethod
    def _generate_update_data(user_config: OptContainerData | UserOptContainerData) -> OptContainerData:
        
        if isinstance(user_config, OptContainerData):
            return user_config

        config = OptContainerConfig.model_validate(
            user_config.model_dump(exclude_unset=True, exclude_none=True)
        )
        return OptContainerData(
            ip = None,
            mc_port = None,
            rcon_port = None,
            config = config
        )