from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from ..data.models.response import MessageResponse, StatusResponse
from ..security import AuthorizationManager, Permission
from .utils import handle_errors

if TYPE_CHECKING:
    from ...gateway.server import Server



class SystemRouter:

    def __init__(self, server: 'Server', auth: AuthorizationManager) -> None:
        self.server = server
        self.auth = auth


    def get_router(self) -> APIRouter:
        
        system_router = APIRouter(prefix="/system", tags=["system"])


        @system_router.get(
            "/status",
            dependencies=[Depends(self.auth.require(Permission.status_get))],
            response_model=StatusResponse,
        )
        @handle_errors
        def fetch_system_status():
            return StatusResponse(
                clients=self.server.get_client_count(),
                sessions=len(self.server._sessions.list()),
                containers=len(self.server._sessions.containers.list()),
                hosts=len(self.server._sessions.containers.hosts.list()),
            )


        @system_router.post(
            "/stop",
            dependencies=[Depends(self.auth.require(Permission.server_manage))],
            response_model=MessageResponse,
        )
        def initiate_server_shutdown():
            self.server._init_shutdown("API request")
            return MessageResponse(message="shutdown initiated")


        return system_router
