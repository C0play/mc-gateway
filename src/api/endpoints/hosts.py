from fastapi import APIRouter, Depends
from pydantic import IPvAnyAddress

from ..models.host import HostData, OptHostData, FullHost
from ..models.response import ListResponse, MessageResponse
from ..services.host import HostService
from .utils import handle_errors


def build_host_admin_router(host_service: HostService, require_manage_hosts) -> APIRouter:
    router = APIRouter(
        prefix="/host",
        tags=["admin: hosts"],
        dependencies=[Depends(require_manage_hosts)],
    )

    @router.post("/add", response_model=HostData)
    @handle_errors
    def host_add_admin(host: FullHost):
        return host_service.host_add_admin(host)

    @router.put("/update/{ip}", response_model=FullHost)
    @handle_errors
    def host_update_admin(ip: IPvAnyAddress, data: OptHostData):
        return host_service.host_update_admin(str(ip), data)

    @router.delete("/remove/{ip}", response_model=FullHost)
    @handle_errors
    def host_remove_admin(ip: IPvAnyAddress):
        return host_service.host_remove_admin(str(ip))

    @router.post("/kick/{ip}", response_model=MessageResponse)
    @handle_errors
    def host_kick_admin(ip: IPvAnyAddress):
        return host_service.host_kick_admin(str(ip))

    @router.get("/list/", response_model=ListResponse)
    @handle_errors
    def host_list_admin(ip: IPvAnyAddress | None = None):
        str_ip = str(ip) if ip is not None else None
        return host_service.host_list_admin(str_ip)

    return router
