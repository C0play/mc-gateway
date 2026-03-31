from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from ..data.models.response import MessageResponse, StatusResponse
from .utils import handle_errors


if TYPE_CHECKING:
    from ...gateway.server import Server


def build_system_admin_router(server: 'Server', require_view_status, require_stop_server) -> APIRouter:
    
    system_router = APIRouter(
        prefix="/system",
        tags=["admin: system"],
    )

    @system_router.get(
        "/status",
        dependencies=[Depends(require_view_status)],
        response_model=StatusResponse,
    )
    @handle_errors
    def system_status_get():
        return StatusResponse(
            clients=server.get_client_count(),
            sessions=len(server._sessions.list()),
            containers=len(server._sessions.containers.list()),
            hosts=len(server._sessions.containers.hosts.list()),
        )

    @system_router.post(
        "/stop",
        dependencies=[Depends(require_stop_server)],
        response_model=MessageResponse,
    )
    def system_shutdown_admin():
        server._init_shutdown("API request")
        return MessageResponse(message="shutdown initiated")

    return system_router
