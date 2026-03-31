from typing import Annotated

from fastapi import APIRouter, Depends

from ..data.models.container import ContainerData, OptContainerData, OptServerConfig, FullContainer
from ..data.models.response import ListResponse, MessageResponse
from ..services.container import ContainerService
from .utils import handle_errors


def build_container_admin_router(container_service: ContainerService, require_manage_containers) -> APIRouter:
    router = APIRouter(
        prefix="/container",
        tags=["admin: containers"],
        dependencies=[Depends(require_manage_containers)],
    )

    @router.post("/add", response_model=FullContainer)
    @handle_errors
    def container_add_admin(data: ContainerData):
        return container_service.container_add_admin(data)

    @router.put("/update/{subdomain}", response_model=FullContainer)
    @handle_errors
    def container_update_admin(subdomain: str, data: OptContainerData):
        return container_service.container_update(subdomain, data)

    @router.delete("/remove/{subdomain}", response_model=FullContainer)
    @handle_errors
    def container_remove_admin(subdomain: str):
        return container_service.container_remove_admin(subdomain)

    @router.post("/kick/{subdomain}", response_model=MessageResponse)
    @handle_errors
    def container_kick_admin(subdomain: str):
        return container_service.container_kick(subdomain)

    @router.get("/list/", response_model=ListResponse)
    @handle_errors
    def container_list_admin(subdomain: str | None = None):
        return container_service.container_list_admin(subdomain)

    return router


def build_container_me_router(
    container_service: ContainerService,
    require_user_manage_own_containers,
    require_session,
) -> APIRouter:
    router = APIRouter(
        prefix="/container",
        tags=["user containers"],
        dependencies=[Depends(require_user_manage_own_containers)],
    )

    @router.get("/list/", response_model=ListResponse)
    @handle_errors
    def container_list_own(
        auth: Annotated[AccessContext, Depends(require_session)],
        subdomain: str | None = None,
    ):
        return container_service.container_list_own(auth.email, subdomain)

    @router.put("/update/{subdomain}", response_model=FullContainer)
    @handle_errors
    def container_update_own(subdomain: str, data: OptServerConfig):
        user_data = OptContainerData.model_validate(
            data.model_dump(exclude_unset=True, exclude_none=True)
        )
        return container_service.container_update(subdomain, user_data)

    @router.get("/get/{subdomain}", response_model=FullContainer)
    @handle_errors
    def container_get_own(subdomain: str):
        return container_service.container_get(subdomain)

    @router.post("/kick/{subdomain}", response_model=MessageResponse)
    @handle_errors
    def container_kick_own(subdomain: str):
        return container_service.container_kick(subdomain)

    return router
