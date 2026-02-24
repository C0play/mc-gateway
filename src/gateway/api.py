import json
import inspect
from socket import socket
from typing import (
    TypedDict,
    TypeAlias,
    Mapping,
    Sequence,
    Callable,
    TYPE_CHECKING,
)

from ..utils.logger import logger
if TYPE_CHECKING:
    from .server import Server


JSON: TypeAlias = Mapping[str, "JSON"] | Sequence["JSON"] | str
class APIResponse(TypedDict):
    code: str
    data: JSON



class API(): 
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
        self.commands: dict[str, Callable[..., APIResponse]] = self._register_commands()


    def execute(self, cmd_name: str, **kwargs) -> APIResponse:
        """
        Executes a command by name, automatically validating arguments against the handler's signature.

        Args:
            cmd_name: The name of the command to execute.
            **kwargs: Arguments to pass to the command handler.

        Returns:
            APIResponse: The result of the command execution or an error message.
        """

        handler = self.commands.get(cmd_name)
        if not handler:
            return API._assemble_res("ERROR", f"unknown command '{cmd_name}'")
        
        try:
            sig = inspect.signature(handler)
            bound_args = sig.bind(**kwargs)
            bound_args.apply_defaults()
            
            return handler(*bound_args.args, **bound_args.kwargs)

        except TypeError as e:
            return API._assemble_res("ERROR", f"invalid arguments: {e}")
        except Exception as e:
            return API._assemble_res("ERROR", f"execution failed: {e}")


    def _register_commands(self) -> dict[str, Callable[..., APIResponse]]:
        return {
            "stop": self._stop,
            "status": self._status,
            "add-player": self._add_player,
            "remove-player": self._remove_player,
            "add-container": self._add_container,
            "remove-container": self._remove_container,
            "add-host": self._add_host,
            "remove-host": self._remove_host,
            "list": self._list,
            "kick-all": self._kick_all,
        }


    @staticmethod
    def _response(
            function: Callable[..., dict[str, str] | tuple | None],
            success_msg: str, error_msg: str 
    ) -> APIResponse:
        try:
            res = function()
        except ValueError as e:
            return API._assemble_res("ERROR", f"invalid arguments: {e}")
        except Exception as e:
            return API._assemble_res("ERROR", error_msg.format(e=e))
        else:
            kwargs = res if isinstance(res, dict) else {}
            return API._assemble_res("OK", success_msg.format(**kwargs))


    @staticmethod
    def _assemble_res(code: str, data: JSON) -> APIResponse:
        return APIResponse(code=code, data=data)


    def _stop(self) -> APIResponse:
        return API._response(
            lambda: (self.server._init_shutdown("API request")),
            "shutdown initiated",
            "shutdown failed"
        )
        

    def _add_player(self, username: str, subdomain: str) -> APIResponse:
        return API._response(
            lambda: self.server._whitelist.storage.create(username, subdomain),
            f"player {username} added to {subdomain}",
            "player addition failed: {e}",
        )


    def _remove_player(self, username: str, subdomain: str) -> APIResponse:
        return API._response(
            lambda: self.server._whitelist.storage.delete(username, subdomain),
            f"player {username} removed from {subdomain}",
            "player removal failed: {e}",
        )
    
    
    def _add_container(self, ip: str, port: int) -> APIResponse:
        return API._response(
            lambda: {"subd": self.server._sessions.containers.storage.create(ip, int(port))},
            "container {ip}:{port} received {subd}",
            "container addition failed: {e}",
        )
    
    
    def _remove_container(self, subdomain: str) -> APIResponse:
        return API._response(
            lambda: (
                self.server._sessions.interrupt("Your server has been removed", subdomain=subdomain),
                self.server._sessions.containers.delete(subdomain)),
            f"container {subdomain} removed",
            "container removal failed: {e}",
        )


    def _add_host(self, ip: str, mac: str, user: str, path: str) -> APIResponse:
        return API._response(
            lambda: self.server._sessions.containers.hostManager.storage.create(ip, mac, user, path),
            "added {ip} to hosts",
            "host addition failed: {e}",
        )


    def _remove_host(self, ip: str) -> APIResponse:
        return API._response(
            lambda: (self.server._sessions.interrupt("Your server has been removed", ip=ip),
                self.server._sessions.containers.hostManager.delete(ip)),
            f"{ip} removed",
            "host removal failed: {e}",
        )

    
    def _kick_all(self, ip: str = "", subdomain: str = "") -> APIResponse:
        
        def kick_logic():
            if bool(ip) == bool(subdomain):
                raise ValueError("specify precisely a single argument")
            self.server._sessions.interrupt(subdomain=subdomain, ip=ip)
            
        return API._response(
            kick_logic,
            "kick failed: {e}",
            f"all players from {subdomain}{ip} learned how to fly"
        )


    def _list(self, resource: str) -> APIResponse:
        lst = None
        match resource:
            case "players":
                lst = self.server._whitelist.storage.list()
            case "containers":
                lst = self.server._sessions.containers.storage.list()
            case "hosts":
                lst = self.server._sessions.containers.hostManager.storage.list()
            case _:
                lst = []

        return API._assemble_res("OK", lst)
    

    def _status(self) -> APIResponse:
        with self.server._client_count_lock:
            return API._assemble_res(
                "OK",
                {
                    "clients": str(self.server._client_count),
                    "sessions": self.server._sessions.list(),
                    "containers": self.server._sessions.containers.list(),
                    "hosts": self.server._sessions.containers.hostManager.list(),
                }
            )



class TCPAdapter():
    """
    Adapts a TCP socket connection to the API class, handling JSON parsing and response sending.
    """

    def __init__(self, api: API) -> None:
        """
        Initializes the adapter.

        Args:
            api: The API instance to execute commands on.
        """
        self.api = api


    def handle(self, socket: socket) -> None:
        """
        Reads a command from the socket and executes it via API.

        Args:
            socket: Socket to receive commands from
        """
        try:
            data = json.loads(socket.recv(1024).decode())
            if not data:
                return

            name = data.get("cmd_name")
            kwargs = data.get("kwargs", {})
            
            resp = self.api.execute(name, **kwargs)

        except Exception as e:
            resp = API._assemble_res("ERROR", str(e))
            name = "unknown"
        
        # Logging
        if name and name != "status":
            if resp.get("code") == "OK":
                logger.info(f"handle_cmd OK: {name}")
            else:
                logger.error(f"handle_cmd {name} -> {resp.get('data')}")

        try:
            socket.sendall(json.dumps(resp).encode())
        except Exception:
            pass
        finally:
            socket.close()