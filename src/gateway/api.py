import re
from functools import wraps
from ipaddress import ip_address
from pathlib import Path
from typing import (
    Literal,
    TYPE_CHECKING,
)

from pydantic_extra_types.mac_address import MacAddress
from pydantic import (
    BaseModel,
    Field,
    RootModel,
    field_validator,
    IPvAnyAddress
)
from fastapi import status as HTTPstatus
from fastapi import (
    FastAPI,
    HTTPException,
    Request
)

from ..utils.logger import logger
if TYPE_CHECKING:
    from .server import Server


# ======================================== PLAYER MODELS ========================================
class PlayerID(BaseModel):
    username: str = Field(..., max_length=50, description="Username of the player")
    subdomain: str = Field(..., min_length=4, max_length=4, description="Server subdomain assigned to the player")


class PlayerData(PlayerID):
    pass


class OptPlayerData(PlayerID):
    pass


# ======================================== HOST MODELS ========================================
class HostID(BaseModel):
    ip: IPvAnyAddress = Field(..., description="IP address of the host machine")


class HostData(HostID):
    mac: MacAddress = Field(..., description="MAC address of the host machine")
    user: str = Field(..., max_length=50, description="User of the host machine")
    path: Path = Field(..., description="Path to the directory containing all minecraft server directories")

    @field_validator('user')
    @classmethod
    def validate_user(cls, v: str) -> str:
        pattern = r"^[a-z_][a-z0-9_-]*$"
        if not re.match(pattern, v):
            raise ValueError('Invalid Linux username')
        return v

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: Path) -> Path:
         if not v.is_absolute():
            raise ValueError('Path must be absolute')
         
         # Basic sanitization check for path traversal or dangerous characters
         # Allow alphanumeric, /, _, -, .
         s = str(v)
         pattern = r"^/[\w\-\./]+$"
         if not re.match(pattern, s) or '..' in s:
              raise ValueError('Invalid path format or characters')
         return v

class OptHostData(HostID):
    mac: str | None = Field(None, min_length=17, max_length=17, description="MAC address of the host machine")
    user: str | None = Field(None, max_length=50, description="User of the host machine")
    path: Path | None = Field(None, description="Path to the directory containing all minecraft server directories")


# ======================================== CONTAINER MODELS ========================================
class ContainerID(BaseModel):
    subdomain: str = Field(..., min_length=4, max_length=4, description="Subdomain assigned to the container")


class ContainerData(BaseModel):
    ip: str = Field(..., min_length=7, max_length=15, description="IP address of the host machine assigned to the container")
    port: int = Field(..., description="Port of the host machine assigned to the container")


class OptContainerData(ContainerID):
    host_ip: str | None = Field(None, min_length=7, max_length=15, description="IP address of the host machine assigned to the container")
    host_port: int | None = Field(None, description="Port of the host machine assigned to the container")


class FullContainer(ContainerID, ContainerData):
    pass


# ======================================== RESPONSE MODELS ========================================
class ListResponse(RootModel):
    root: list[PlayerData] | list[FullContainer] | list[HostData] = Field(
        ...,
        description="List of requested resources"
    )


class KickRequest(BaseModel):
    ip: str | None = Field(None, min_length=7, max_length=15, description="IP of the host to kick all players safely from")
    subdomain: str | None = Field(None, min_length=4, max_length=4, description="Subdomain of the container to kick all players from")


class StatusResponse(BaseModel):
    clients: int
    sessions: int
    containers: int
    hosts: int


class MessageResponse(BaseModel):
    message: str


# ======================================== HELPERS ========================================
def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        operation = func.__name__.replace("_", " ")
        try:
            return func(*args, **kwargs)
        except (KeyError, ValueError) as e:
            logger.info(f"API: invalid request ({operation}): {e}")
            raise HTTPException(
                status_code=HTTPstatus.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API: failed to {operation}: {e}")
            raise HTTPException(
                status_code=HTTPstatus.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return wrapper


# ======================================== FastAPI ========================================
class API:
    """
    Handles command execution for the gateway server via the control interface.
    """

    def __init__(self, server: 'Server') -> None:
        """
        Initializes the API with a reference to the server.

        Args:
            server: The server instance to control.
        """
        self.server = server
        self.app = FastAPI(title="mc-gateway API")
        
        self._register()
    


    def _register(self) -> None:
        
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            client_ip = request.client.host if request.client else "unknown"
            try:
                response = await call_next(request)
                
                if request.url.path not in ("/status", "/favicon.ico"):
                    logger.info(f"API: {request.method:<7} {request.url.path} from {client_ip} : {response.status_code}")
                
                return response
            except Exception as e:
                logger.error(f"API: error processing {request.url.path}: {e}")
                raise e


        @self.app.post("/player/add", response_model=PlayerData)
        @handle_errors
        def add_player(player: PlayerData):
            self.server._whitelist.storage.create(player.username, player.subdomain)
            return PlayerData(username=player.username, subdomain=player.subdomain)
        

        @self.app.delete("/player/remove", response_model=PlayerID)
        @handle_errors
        def remove_player(player: PlayerID):
            self.server._whitelist.storage.delete(player.username, player.subdomain)
            return player


        @self.app.post("/container/add", response_model=FullContainer)
        @handle_errors
        def add_container(container: ContainerData):
            subd = self.server._sessions.containers.storage.create(container.ip, container.port)
            return FullContainer(subdomain=subd, **container.model_dump())


        @self.app.delete("/container/remove", response_model=ContainerID)
        @handle_errors
        def remove_container(container: ContainerID):
            self.server._sessions.interrupt("Your server has been removed", subdomain=container.subdomain)
            self.server._sessions.containers.delete(container.subdomain)
            return container


        @self.app.post("/host/add", response_model=HostData)
        @handle_errors
        def add_host(host: HostData):
            self.server._sessions.containers.hosts.storage.create(
                str(host.ip), str(host.mac), host.user, str(host.path)
            )
            return host


        @self.app.delete("/host/remove", response_model=HostID)
        @handle_errors
        def remove_host(host: HostID):
            self.server._sessions.interrupt("Your server has been removed", ip=str(host.ip))
            self.server._sessions.containers.hosts.delete(str(host.ip))
            return host



        @self.app.post("/kick", response_model=MessageResponse)
        @handle_errors
        def kick_all(target: KickRequest):
            if bool(target.ip) == bool(target.subdomain):
                raise ValueError("specify precisely a single argument (ip OR subdomain)")
            
            self.server._sessions.interrupt(subdomain=target.subdomain or "", ip=target.ip or "")
            return MessageResponse(message=f"all players from {target.subdomain}{target.ip} kicked")


        @self.app.get("/status", response_model=StatusResponse)
        @handle_errors
        def status():
            return StatusResponse(
                clients=self.server.get_client_count(), 
                sessions=len(self.server._sessions.list()),
                containers=len(self.server._sessions.containers.list()), 
                hosts=len(self.server._sessions.containers.hosts.list()),
            )

            

        @self.app.get("/list/{resource}", response_model=ListResponse)
        @handle_errors
        def list(resource: Literal["players", "hosts", "containers"]):
            lst = []
            match resource:
                case "players":
                    query = self.server._whitelist.storage.list()
                    lst = [PlayerData(**row) for row in query]
                case "containers":
                    query = self.server._sessions.containers.storage.list()
                    lst = [FullContainer(**{
                            **row,
                            "port": int(row["port"])
                        }) for row in query]
                case "hosts":
                    query = self.server._sessions.containers.hosts.storage.list()
                    lst = [HostData(**{
                        **row,
                        "ip": ip_address(row["ip"]),
                        "mac": MacAddress(row["mac"]),
                        "path": Path(row["path"])
                        }) for row in query]
            return ListResponse(root=lst)
            
        
        @self.app.post("/stop", response_model=MessageResponse)
        def stop():
            self.server._init_shutdown("API request")
            return MessageResponse(message="shutdown initiated")        