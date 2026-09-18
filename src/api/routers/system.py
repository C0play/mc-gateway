from typing import TYPE_CHECKING

from fastapi import APIRouter, Security, status

from src.utils.logger import logger

from ..data.models.response import MessageResponse
from ..data.models.system import StatusResponse, TaskInfo
from ..security import AuthorizationManager, Permission

if TYPE_CHECKING:
    from ...gateway.server import Server


class SystemRouter:
    """Defines API endpoints used for system management."""

    def __init__(self, server: "Server", auth: AuthorizationManager) -> None:
        self.server = server
        self.auth = auth

    def get_router(self) -> APIRouter:

        system_router = APIRouter(prefix="/system", tags=["system"])

        REQ = self.auth.require

        @system_router.get(
            "/status",
            dependencies=[Security(REQ, scopes=[Permission.system_status_read])],
            response_model=StatusResponse,
        )
        def fetch_system_status():
            return StatusResponse(
                clients=self.server.get_client_count(),
                sessions=len(self.server._sessions.list()),
                containers=len(self.server._sessions.containers.list()),
                hosts=len(self.server._sessions.containers.hosts.list()),
            )

        @system_router.post(
            "/stop",
            dependencies=[Security(REQ, scopes=[Permission.system_manage])],
            response_model=MessageResponse,
        )
        def initiate_server_shutdown():
            self.server._init_shutdown("API request")
            return MessageResponse(message="shutdown initiated")

        @system_router.post(
            "/task/completed",
            status_code=status.HTTP_204_NO_CONTENT,
        )
        def taks_completed(task: TaskInfo):
            container = self.server._sessions.containers.get_by_name(task.container_name)
            container.set_event(task.job)
            logger.info(
                f"{container}: task {task.id:6} finished with status '{task.status}'"
            )

        return system_router
