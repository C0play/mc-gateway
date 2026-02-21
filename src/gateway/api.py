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

    def __init__(self, server: 'Server') -> None:
        self.server = server
        self.commands: dict[str, Callable[..., APIResponse]] = self._register_commands()


    def execute(self, cmd_name: str, **kwargs) -> APIResponse:
        """Executes a command by name, automatically validating arguments."""

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
        }



    def _stop(self) -> APIResponse:
        self.server._shutdown = True
        return API._assemble_res("OK", "shutdown initiated")
    

    def _status(self) -> APIResponse:
        with self.server._client_count_lock:
            return API._assemble_res("OK", str(self.server._client_count))


    def _add_player(self, username: str, subdomain: str) -> APIResponse:
        try:
            self.server._whitelist.storage.create(username, subdomain)
        except Exception as e:
            return API._assemble_res("ERROR", f"player addition failed: {e}")
        else:
           return API._assemble_res("OK", f"player {username} added to {subdomain}")


    def _remove_player(self, username: str, subdomain: str) -> APIResponse:
        try:
            self.server._whitelist.storage.delete(username, subdomain)
        except Exception as e:
            return API._assemble_res("ERROR", f"player removal failed: {e}")
        else:
            return API._assemble_res("OK", f"player {username} removed from {subdomain}")
    
    
    def _add_container(self, ip: str, port: int) -> APIResponse:
        try:
            server_subdomain = self.server._sessions.containers.storage.create(ip, int(port))
        except Exception as e:
            return API._assemble_res("ERROR", f"container addition failed: {e}")
        else:
            return API._assemble_res("OK", f"container {ip}:{port} received {server_subdomain}")
    
    
    def _remove_container(self, subdomain: str) -> APIResponse:
        try:
            self.server._sessions.containers.storage.delete(subdomain)
        except Exception as e:
            return API._assemble_res("ERROR", f"container removal failed: {e}")
        else:
            return API._assemble_res("ERROR", f"container {subdomain} removed")


    def _add_host(self, ip: str, mac: str, user: str, path: str) -> APIResponse:
        try:
            self.server._sessions.containers.hostManager.storage.add(ip, mac, user, path)
        except Exception as e:
            return API._assemble_res("ERROR", f"host addition failed: {e}")
        else:
            return API._assemble_res("ERROR", f"added {ip} to hosts")


    def _remove_host(self, ip: str) -> APIResponse:
        try:
            self.server._sessions.containers.hostManager.storage.remove(ip)
        except Exception as e:
            return API._assemble_res("OK", f"host removal failed: {e}")
        else:
            return API._assemble_res("OK", f"{ip} removed")

    
    def _list(self) -> APIResponse:
        return API._assemble_res(
            "OK", 
            {
                "players": self.server._whitelist.storage.dict(), 
                "containers": self.server._sessions.containers.storage.dict(),
                "hosts": self.server._sessions.containers.hostManager.storage.dict()
            }
        )


    @staticmethod
    def _assemble_res(code: str, data: JSON) -> APIResponse:
        return APIResponse(code=code, data=data)



class TCPAdater():

    def __init__(self, api: API) -> None:
        self.api = api


    def handle(self, socket: socket) -> None:
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