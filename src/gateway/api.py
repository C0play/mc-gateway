from functools import wraps
from ipaddress import ip_address
from pathlib import Path
from typing import (
    Literal,
    cast,
    TYPE_CHECKING,
)

from pydantic_extra_types.mac_address import MacAddress
from pydantic import (
    BaseModel,
    Field,
    RootModel,
    field_validator,
    model_validator,
    IPvAnyAddress
)
from fastapi import status as HTTPstatus
from fastapi import (
    FastAPI,
    HTTPException,
    Request
)

from ..utils.keygen import KeyGenerator
from ..utils.logger import logger
from ..utils.validators import (
    validate_linux_user,
    validate_absolute_path,
    validate_subdomain,
    check_path_user_consistency
)
from ..utils.composegen import (
    ComposeConfig,
    OptComposeConfig,
    PERFORMANCE_MODS
)
if TYPE_CHECKING:
    from .server import Server


# ======================================== PLAYER MODELS ========================================
class PlayerID(BaseModel):
    username: str = Field(..., max_length=50, description="Username of the player")
    subdomain: str = Field(..., min_length=4, max_length=4, description="Server subdomain assigned to the player")

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        return validate_subdomain(v)


class PlayerData(PlayerID):
    pass


class OptPlayerData(PlayerID):
    pass


# ======================================== HOST MODELS ========================================
class HostID(BaseModel):
    ip: IPvAnyAddress = Field(..., description="IP address of the host machine")


class HostData(BaseModel):
    mac: MacAddress = Field(..., description="MAC address of the host machine")
    user: str = Field(..., max_length=50, description="User of the host machine")
    path: Path = Field(..., description="Path to the directory containing all minecraft server directories")

    @field_validator('user')
    @classmethod
    def validate_user(cls, v: str) -> str:
        return validate_linux_user(v)

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        return validate_absolute_path(v)

    @model_validator(mode='after')
    def validate_path_user_consistency(self) -> 'HostData':
        check_path_user_consistency(self.user, self.path)
        return self


class OptHostData(BaseModel):
    mac: MacAddress | None = Field(None, description="MAC address of the host machine")
    user: str | None = Field(None, max_length=50, description="User of the host machine")
    path: Path | None = Field(None, description="Path to the directory containing all minecraft server directories")

    @field_validator('user')
    @classmethod
    def validate_user(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_linux_user(v)
        return v

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: Path | None) -> Path | None:
        if v is not None:
            return validate_absolute_path(v)
        return v

    @model_validator(mode='after')
    def validate_path_user_consistency(self) -> 'OptHostData':
        check_path_user_consistency(self.user, self.path)
        return self


class FullHost(HostID, HostData):
    pass


# ======================================== CONTAINER MODELS ========================================
class ContainerID(BaseModel):
    subdomain: str = Field(..., min_length=4, max_length=4, description="Subdomain assigned to the container")

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        return validate_subdomain(v)


class ContainerData(BaseModel):
    ip: IPvAnyAddress = Field(..., description="IP address of the host machine assigned to the container")
    mc_port: int = Field(..., description="Minecraft port of the host machine assigned to the container")
    rcon_port: int = Field(..., description="RCON port of the host machine assigned to the container")


class OptContainerData(BaseModel):
    ip: IPvAnyAddress | None = Field(None, description="IP address of the host machine assigned to the container")
    mc_port: int | None = Field(None, description="Minecraft port of the host machine assigned to the container")
    rcon_port: int | None = Field(None, description="RCON port of the host machine assigned to the container")


class FullContainer(ContainerID, ContainerData):
    initialized: bool = Field(..., description="Flag whether compose.yml was deployed on the host")
    to_be_deleted: bool = Field(..., description="Flag whether container is set to be deleted")
    config: ComposeConfig = Field(..., description="Configuration used to generate compose.yml")


class ContainerCreateRequest(ContainerData):
    config: ComposeConfig = Field(..., description="YAML file variables to use for server confguration")


class ContainerUpdateRequest(OptContainerData):
    config: OptComposeConfig = Field(..., description="YAML file variables to use for server confguration")


# ======================================== RESPONSE MODELS ========================================
class ListResponse(RootModel):
    root: list[PlayerData] | list[FullContainer] | list[HostData] = Field(
        ...,
        description="List of requested resources"
    )


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
    def endpoint_wrapper(*args, **kwargs):
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
    return endpoint_wrapper


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
                    logger.info(f"API: {client_ip} - {request.method:<7} {request.url.path} "
                                + f"{response.status_code}")
                
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
            self.server._sessions.interrupt(
                reason="You were removed from the wgitelist",
                username=player.username
            )
            self.server._whitelist.storage.delete(player.username, player.subdomain)
            return player
        
        
        @self.app.post("/player/kick/{username}", response_model=MessageResponse)
        @handle_errors
        def kick_player(username: str):
            self.server._sessions.interrupt(username=username)
            return MessageResponse(
                message=f"Player {username} has been kicked"
            )


        @self.app.post("/container/add", response_model=FullContainer)
        @handle_errors
        def add_container(data: ContainerCreateRequest):
            for mod in PERFORMANCE_MODS:
                if mod not in data.config.modrinth_projects:
                    data.config.modrinth_projects.append(mod)
            
            container = self.server._sessions.containers.create(
                str(data.ip),
                data.mc_port,
                data.rcon_port,
                data.config
            )
            return FullContainer(
                subdomain=str(container.subdomain),
                ip=data.ip,
                mc_port=data.mc_port,
                rcon_port=data.rcon_port,
                initialized=False,
                to_be_deleted=False,
                config=data.config
            )


        @self.app.put("/container/update/{subdomain}", response_model=FullContainer)
        @handle_errors
        def update_container(subdomain: str, data: ContainerUpdateRequest):
            if not KeyGenerator.validate(subdomain):
                raise ValueError(f"subdomain is not valid")
            
            containers = self.server._sessions.containers.storage.read(subdomain=subdomain)
            if not containers:
                 raise KeyError(f"container {subdomain} does not exist")
            old_container = containers[0]

            update_fields = {}
            if data.ip:
                update_fields['host'] = str(data.ip)
            if data.mc_port:
                update_fields['mc_port'] = data.mc_port
            if data.rcon_port:
                update_fields['rcon_port'] = data.rcon_port

            # Merge config fields
            current_cfg = ComposeConfig.model_validate_json(str(old_container.config))
            updates = data.config.model_dump(exclude_unset=True)
            
            if updates:
                merged_dict = current_cfg.model_dump()
                for k, v in updates.items():
                    if v is not None:
                        merged_dict[k] = v
                
                new_cfg_obj = ComposeConfig(**merged_dict)
                
                for mod in PERFORMANCE_MODS:
                    if mod not in new_cfg_obj.modrinth_projects:
                        new_cfg_obj.modrinth_projects.append(mod)

                update_fields['config'] = new_cfg_obj.model_dump_json()
            else:
                new_cfg_obj = current_cfg

            if update_fields:
                update_fields["initialized"] = False
                updated_container = self.server._sessions.containers.storage.update(
                    subdomain, **update_fields
                )
            else:
                updated_container = old_container

            return FullContainer(
                subdomain = str(updated_container.subdomain),
                ip = updated_container.host.ip,
                mc_port = cast(int, updated_container.mc_port),
                rcon_port = cast(int, updated_container.rcon_port),
                initialized = bool(updated_container.initialized),
                to_be_deleted = bool(updated_container.to_be_deleted),
                config = new_cfg_obj
            )


        @self.app.delete("/container/remove", response_model=ContainerID)
        @handle_errors
        def remove_container(container: ContainerID):
            self.server._sessions.interrupt(
                "Your server has been removed",
                subdomain=container.subdomain
            )
            self.server._sessions.containers.delete(container.subdomain)
            return container
        
        
        @self.app.post("/container/kick/{subdomain}", response_model=MessageResponse)
        @handle_errors
        def kick_from_container(subdomain: str):
            self.server._sessions.interrupt(subdomain=subdomain)
            return MessageResponse(
                message=f"All players from server {subdomain} have been kicked"
            )


        @self.app.post("/host/add", response_model=HostData)
        @handle_errors
        def add_host(host: FullHost):
            self.server._sessions.containers.hosts.storage.create(
                str(host.ip), str(host.mac), host.user, str(host.path)
            )
            return host
        
        
        @self.app.put("/host/update/{ip}", response_model=FullHost)
        @handle_errors
        def update_host(ip: IPvAnyAddress, data: OptHostData):
            updates = data.model_dump(exclude_unset=True)
            new_host = self.server._sessions.containers.hosts.storage.update(
                str(ip), **updates
            )
            return FullHost(
                ip=ip,
                mac=MacAddress(new_host.mac),
                user=str(new_host.user),
                path=Path(str(new_host.path)),
            )

        
        @self.app.delete("/host/remove", response_model=HostID)
        @handle_errors
        def remove_host(host: HostID):
            self.server._sessions.interrupt(
                "Your server has been removed",
                ip=str(host.ip)
            )
            self.server._sessions.containers.hosts.delete(str(host.ip))
            return host


        @self.app.post("/host/kick/{ip}", response_model=MessageResponse)
        @handle_errors
        def kick_from_host(ip: IPvAnyAddress):
            self.server._sessions.interrupt(ip=str(ip))
            return MessageResponse(
                message=f"All players from {ip} have been kicked"
            )


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

            if resource == "players":
                query = self.server._whitelist.storage.list()
                lst = [PlayerData(**row) for row in query]

            elif resource == "containers":
                query = self.server._sessions.containers.storage.list()
                lst = [FullContainer(**{
                        **row,
                        "mc_port": int(row["mc_port"]),
                        "rcon_port": int(row["rcon_port"]),
                        "config": ComposeConfig.model_validate_json(row["config"])
                    }) for row in query]
                
            elif resource == "hosts":
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