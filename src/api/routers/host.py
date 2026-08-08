from fastapi import APIRouter, Security
from pydantic import IPvAnyAddress

from ..data.models.host import HostData, OptHostData, FullHost
from ..data.models.response import MessageResponse
from ..services.host import HostService
from ..security import AuthorizationManager, Permission



class HostRouter:
    """Defines API endpoints used for host management."""

    def __init__(self, host_service: HostService, auth: AuthorizationManager) -> None:
        self.hosts = host_service
        self.auth = auth


    def get_router(self) -> APIRouter:
        
        router = APIRouter(prefix="/hosts", tags=["hosts"])

        REQ = self.auth.require

        @router.post(
            "/",
            dependencies=[Security(REQ, scopes=[Permission.host_create])],
            response_model=HostData
        )
        def create_host(host: FullHost):
            return self.hosts.add(host)


        @router.get(
            "/",
            dependencies=[Security(REQ, scopes=[Permission.host_read])],
            response_model=list[FullHost]
        )
        def fetch_host(ip: IPvAnyAddress | None = None):
            str_ip = str(ip) if ip is not None else None
            return self.hosts.read(str_ip)


        @router.patch(
            "/{ip}",
            dependencies=[Security(REQ, scopes=[Permission.host_update])],
            response_model=FullHost
        )
        def update_host(ip: IPvAnyAddress, data: OptHostData):
            return self.hosts.update(str(ip), data)


        @router.delete(
            "/{ip}",
            dependencies=[Security(REQ, scopes=[Permission.host_delete])],
            response_model=FullHost
        )
        def remove_host(ip: IPvAnyAddress):
            return self.hosts.remove(str(ip))


        @router.post(
            "/{ip}/kick",
            dependencies=[Security(REQ, scopes=[Permission.host_kick])],
            response_model=MessageResponse
        )
        def kick_all_from_host(ip: IPvAnyAddress):
            return self.hosts.kick(str(ip))


        return router
