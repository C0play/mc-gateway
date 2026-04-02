from fastapi import APIRouter, Depends
from pydantic import IPvAnyAddress

from ..data.models.host import HostData, OptHostData, FullHost
from ..data.models.response import ListResponse, MessageResponse
from ..services.host import HostService
from .utils import handle_errors
from ..security import AuthorizationManager, Permission


class HostRouter:

    def __init__(self, host_service: HostService, auth: AuthorizationManager) -> None:
        self.host_service = host_service
        self.auth = auth


    def build_host_admin_router(self) -> APIRouter:
        
        MANAGE_ALL = self.auth.require(Permission.host_manage_all)

        router = APIRouter(
            prefix="/host",
            dependencies=[Depends(MANAGE_ALL)] 
        )

        @router.post("/add", response_model=HostData)
        @handle_errors
        def host_add(host: FullHost):
            return self.host_service.host_add(host)


        @router.put("/update/{ip}", response_model=FullHost)
        @handle_errors
        def host_update(ip: IPvAnyAddress, data: OptHostData):
            return self.host_service.host_update(str(ip), data)


        @router.delete("/remove/{ip}", response_model=FullHost)
        @handle_errors
        def host_remove(ip: IPvAnyAddress):
            return self.host_service.host_remove(str(ip))

        @router.post("/kick/{ip}", response_model=MessageResponse)
        @handle_errors
        def host_kick(ip: IPvAnyAddress):
            return self.host_service.host_kick(str(ip))

        @router.get("/list/", response_model=ListResponse)
        @handle_errors
        def host_get(ip: IPvAnyAddress | None = None):
            str_ip = str(ip) if ip is not None else None
            return self.host_service.host_list(str_ip)

        return router
