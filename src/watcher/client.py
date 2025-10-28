import socket
from enum import IntEnum

class state(IntEnum):
    Null = 0
    Status = 1
    Login = 2
    Transfer = 3

class Client:
    def __init__(self, client_socket: socket.socket, addr: tuple[str, int]) -> None:
        self.socket = client_socket
        self.ip = addr[0]
        self.port = addr[1]
        self.state = state.Null

    def __eq__(self, other) -> bool:
        if not isinstance(other, Client):
            return False
        return self.port == other.port if self.ip == other.ip else False
    
    def __hash__(self) -> int:
        return hash((self.ip, self.port))
    
    def __repr__(self) -> str:
        return f"Client<ip={self.ip}, port={self.port}>"
    
    def __str__(self) -> str:
        return f"Client<{self.ip}, {self.port}>"
    
    def updateState(self, newState: int)  -> None:
        self.state = newState