import socket
from enum import IntEnum

from ..utils.logger import logger



class State(IntEnum):
    Null = 0
    Status = 1
    Login = 2
    Transfer = 3



class Client():
    """
    Represents a connected Minecraft client.
    Stores socket information, protocol state, and authentication details.
    """

    def __init__(self, client_socket: socket.socket, addr: tuple[str, int]) -> None:
        """
        Initializes the Client with a socket and address.

        Args:
            client_socket: The client's socket object.
            addr: A tuple containing (ip, port).
        """
        self.socket = client_socket
        self.ip = addr[0]
        self.port = addr[1]

        self.username: str | None = None
        self.subdomain: str | None = None
        
        self.state = State.Null


    def updateState(self, newState: int)  -> None:
        """Updates the protocol state of the client."""
        self.state = newState


    def close(self):
        """Closes the client socket."""
        try:
            self.socket.close()
        except Exception as e:
            logger.error(f"{self} closing client failed: {e}")
            raise RuntimeError(f"{self} closing client {e}")
    

    def __eq__(self, other) -> bool:
        if not isinstance(other, Client):
            return False
        return self.port == other.port if self.ip == other.ip else False


    def __hash__(self) -> int:
        return hash((self.ip, self.port))


    def __str__(self) -> str:
        return f"Client<{self.ip}, {self.port}, {self.username}, {self.subdomain}>"

