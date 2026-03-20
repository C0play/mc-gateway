from functools import wraps
from ipaddress import ip_address
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
from ..utils.composegen import PERFORMANCE_MODS
from ..utils.config_merge import merge_partial_model
from ..utils.validators import validate_container_ram_against_host
from ..whitelist.models import (
    PlayerID,
    PlayerData,
)
from ..container.models import (
    ContainerData,
    OptContainerData,
    FullContainer,
    ContainerConfig,
)
from ..host.models import (
    HostData,
    OptHostData,
    FullHost,
    HostConfig
)

if TYPE_CHECKING:
    from .server import Server



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
        self.hosts = server._sessions.containers.hosts
        self.containers = server._sessions.containers
        self.whitelist = server._whitelist
        self.sessions = server._sessions
        self.app = FastAPI(title="mc-gateway API")
        
        self._register()
    


    def _register(self) -> None:
        
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            client_ip = request.client.host if request.client else "unknown"
            try:
                response = await call_next(request)
                
                if request.url.path not in ("/status", "/favicon.ico"):
                    logger.info(f"API: {client_ip} - [{response.status_code}] {request.method:<7} {request.url.path}")
                
                return response
            except Exception as e:
                logger.error(f"API: error processing {request.url.path}: {e}")
                raise e


        @self.app.post("/player/add", response_model=PlayerData)
        @handle_errors
        def add_player(player: PlayerData):
            self.whitelist.storage.create(player.username, player.subdomain)
            return PlayerData(username=player.username, subdomain=player.subdomain)
        

        @self.app.delete("/player/remove", response_model=PlayerID)
        @handle_errors
        def remove_player(player: PlayerID):
            self.sessions.interrupt(
                reason="You were removed from the wgitelist",
                username=player.username
            )
            self.whitelist.storage.delete(player.username, player.subdomain)
            return player
        
        
        @self.app.post("/player/kick/{username}", response_model=MessageResponse)
        @handle_errors
        def kick_player(username: str):
            self.sessions.interrupt(username=username)
            return MessageResponse(
                message=f"Player {username} has been kicked"
            )


        @self.app.post("/container/add", response_model=FullContainer)
        @handle_errors
        def add_container(data: ContainerData):
            for mod in PERFORMANCE_MODS:
                if mod not in data.config.modrinth_projects:
                    data.config.modrinth_projects.append(mod)

            host_record = self.hosts.storage.read(ip=str(data.ip))[0]
            host_cfg = HostConfig.model_validate(host_record.config)
            validate_container_ram_against_host(host_cfg, data.config)
            
            container = self.containers.create(
                str(data.ip),
                data.mc_port,
                data.rcon_port,
                data.config
            )
            return FullContainer(
                subdomain=str(container.subdomain),
                mc_port=data.mc_port,
                rcon_port=data.rcon_port,
                ip=data.ip,
                config=data.config,
                initialized=False,
                to_be_deleted=False,
            )


        @self.app.put("/container/update/{subdomain}", response_model=FullContainer)
        @handle_errors
        def update_container(subdomain: str, data: OptContainerData):
            if not KeyGenerator.validate(subdomain):
                raise ValueError(f"subdomain is not valid")
            
            old_container = self.containers.storage.read(subdomain=subdomain)[0]

            old_cfg = ContainerConfig.model_validate(old_container.config)
            new_cfg = merge_partial_model(old_cfg, data.config)

            for mod in PERFORMANCE_MODS:
                if mod not in new_cfg.modrinth_projects:
                    new_cfg.modrinth_projects.append(mod)

            target_ip = str(data.ip) if data.ip else str(old_container.host.ip)
            host = self.hosts.storage.read(ip=target_ip)[0]
            host_cfg = HostConfig.model_validate(host.config)
            validate_container_ram_against_host(host_cfg, new_cfg)

            container_updates = data.model_dump(exclude_unset=True, exclude_none=True)
            update_fields: dict = {**container_updates, "config": new_cfg.model_dump(mode="json")}

            if "ip" in update_fields:
                update_fields["host"] = str(update_fields.pop("ip"))

            update_fields["initialized"] = False

            updated_container = self.containers.storage.update(
                subdomain, **update_fields
            )

            return FullContainer(
                subdomain = str(updated_container.subdomain),
                ip = updated_container.host.ip,
                mc_port = cast(int, updated_container.mc_port),
                rcon_port = cast(int, updated_container.rcon_port),
                initialized = bool(updated_container.initialized),
                to_be_deleted = bool(updated_container.to_be_deleted),
                config = new_cfg,
            )


        @self.app.delete("/container/remove/{subdomain}", response_model=FullContainer)
        @handle_errors
        def remove_container(subdomain: str):
            deleted_container = self.containers.storage.read(subdomain=subdomain)[0]
            
            self.sessions.interrupt(
                "Your server has been removed",
                subdomain=subdomain
            )
            self.containers.delete(subdomain)

            return FullContainer(
                subdomain = str(deleted_container.subdomain),
                ip = deleted_container.host.ip,
                mc_port=cast(int, deleted_container.mc_port),
                rcon_port=cast(int, deleted_container.rcon_port),
                initialized = bool(deleted_container.initialized),
                to_be_deleted = bool(deleted_container.to_be_deleted),
                config = ContainerConfig.model_validate(deleted_container.config),
            )

        
        
        @self.app.post("/container/kick/{subdomain}", response_model=MessageResponse)
        @handle_errors
        def kick_from_container(subdomain: str):
            self.sessions.interrupt(subdomain=subdomain)
            return MessageResponse(
                message=f"All players from server {subdomain} have been kicked"
            )


        @self.app.post("/host/add", response_model=HostData)
        @handle_errors
        def add_host(host: FullHost):
            config_json = host.config.model_dump(mode="json")
            self.hosts.storage.create(
                str(host.ip), str(host.mac), host.config.user, 
                str(host.config.path), config_json,
            )
            return host
        
        
        @self.app.put("/host/update/{ip}", response_model=FullHost)
        @handle_errors
        def update_host(ip: IPvAnyAddress, data: OptHostData):
            updates = data.model_dump(exclude_unset=True, exclude_none=True)

            if data.config is not None:
                curr_host = self.hosts.storage.read(ip=str(ip))[0]
                curr_cfg = HostConfig.model_validate(curr_host.config)
                new_cfg = merge_partial_model(curr_cfg, data.config)
                updates['config'] = new_cfg.model_dump(mode="json")

            new_host = self.hosts.storage.update(str(ip), **updates)

            return FullHost(
                ip=ip,
                mac=MacAddress(new_host.mac),
                config=HostConfig.model_validate(new_host.config),
            )

        
        @self.app.delete("/host/remove/{ip}", response_model=FullHost)
        @handle_errors
        def remove_host(ip: IPvAnyAddress):
            deleted_host = self.hosts.storage.read(ip=str(ip))[0]
            
            self.sessions.interrupt(
                "Your server has been removed",
                ip=str(ip)
            )
            self.hosts.delete(str(ip))

            return FullHost(
                ip=ip,
                mac=MacAddress(deleted_host.mac),
                config=HostConfig.model_validate(deleted_host.config),
            )


        @self.app.post("/host/kick/{ip}", response_model=MessageResponse)
        @handle_errors
        def kick_from_host(ip: IPvAnyAddress):
            self.sessions.interrupt(ip=str(ip))
            return MessageResponse(
                message=f"All players from {ip} have been kicked"
            )


        @self.app.get("/status", response_model=StatusResponse)
        @handle_errors
        def status():
            return StatusResponse(
                clients=self.server.get_client_count(), 
                sessions=len(self.sessions.list()),
                containers=len(self.containers.list()), 
                hosts=len(self.hosts.list()),
            )


        @self.app.get("/list/{resource}", response_model=ListResponse)
        @handle_errors
        def list(resource: Literal["players", "hosts", "containers"]):
            lst = []

            if resource == "players":
                query = self.whitelist.storage.list()
                lst = [PlayerData(**row) for row in query]

            elif resource == "containers":
                query = self.containers.storage.list()
                lst = [FullContainer(**{
                        **row,
                        "config": ContainerConfig.model_validate(row["config"])
                    }) for row in query]
                
            elif resource == "hosts":
                query = self.hosts.storage.list()
                lst = [HostData(**{
                    **row,
                    "ip": ip_address(row["ip"]),
                    "mac": MacAddress(row["mac"]),
                    "config": HostConfig.model_validate(row["config"]),
                    }) for row in query]
                
            return ListResponse(root=lst)
            
        
        @self.app.post("/stop", response_model=MessageResponse)
        def stop():
            self.server._init_shutdown("API request")
            return MessageResponse(message="shutdown initiated")        