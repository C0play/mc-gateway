from fastapi import APIRouter, Depends
from pydantic import IPvAnyAddress

from ..data.models.host import HostData, OptHostData, FullHost
from ..data.models.response import ListResponse, MessageResponse
from ..services.host import HostService
from .utils import handle_errors
from ..security import AuthorizationManager, Permission



class HostRouter:

    def __init__(self, host_service: HostService, auth: AuthorizationManager) -> None:
        self.hosts = host_service
        self.auth = auth


    def get_router(self) -> APIRouter:
        
        router = APIRouter(
            prefix="/host",
            tags=["hosts"],
            dependencies=[Depends(self.auth.require(Permission.host_manage_all))] 
        )

        @router.post("/add", response_model=HostData)
        @handle_errors
        def create_host(host: FullHost):
            return self.hosts.add(host)


        @router.put("/update/{ip}", response_model=FullHost)
        @handle_errors
        def update_host(ip: IPvAnyAddress, data: OptHostData):
            return self.hosts.update(str(ip), data)


        @router.delete("/remove/{ip}", response_model=FullHost)
        @handle_errors
        def remove_host(ip: IPvAnyAddress):
            return self.hosts.remove(str(ip))


        @router.post("/kick/{ip}", response_model=MessageResponse)
        @handle_errors
        def kick_all_from_host(ip: IPvAnyAddress):
            return self.hosts.kick(str(ip))


        @router.get("/list", response_model=ListResponse)
        @handle_errors
        def fetch_host(ip: IPvAnyAddress | None = None):
            str_ip = str(ip) if ip is not None else None
            return self.hosts.read(str_ip)

        return router
