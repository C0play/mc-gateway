import socket

from ..protocol.protocol import BaseProtocol


class Client:
    """
    Represents a connected Minecraft client.
    Stores socket information, protocol state, and authentication details.
    """

    def __init__(
        self,
        client_socket: socket.socket,
        addr: tuple[str, int],
        protocol: BaseProtocol,
    ) -> None:
        """
        Initializes the Client with a socket and address.

        Args:
            client_socket: The client's socket object.
            addr: A tuple containing (ip, mc_port).
        """
        self.socket = client_socket
        self.ip = addr[0]
        self.mc_port = addr[1]
        self.packets: BaseProtocol = protocol

        self.username: str | None = None
        self.subdomain: str | None = None


    def close(self):
        """Closes the client socket."""
        try:
            self.socket.close()
        except Exception as e:
            raise ConnectionError(f"{self} failed to close socket: {e}")


    def __eq__(self, other) -> bool:
        if not isinstance(other, Client):
            return False
        return self.mc_port == other.mc_port if self.ip == other.ip else False


    def __hash__(self) -> int:
        return hash((self.ip, self.mc_port))


    def __str__(self) -> str:
        unam_str = ", " + self.username if self.username else ""
        subd_str = ", " + self.subdomain if self.subdomain else ""
        return f"Client<{self.ip}, {self.mc_port}" + unam_str + subd_str + ">"
