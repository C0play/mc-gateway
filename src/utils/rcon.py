import socket
import random


class RCON:
    """
    Provides methods to send RCON commands to Minecraft servers\n
    **Example**:
        
        with RCON(192.168.0.1, 25575, "password") as rcon:
            rcon.login()
            rcon.send("/seed")
        
            
    """

    def __init__(self, host: str, port: int, password: str) -> None:
        """
        Initializes the RCON client.

        Args:
            host: The IP of the host on which the minecraft server is running.
            port: The port of the RCON server.
            password: Password for the RCON server.
        """

        self.host = host
        self.port = port
        self.password = password
        self.socket: socket.socket


    def __enter__(self):
        self._connect()
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self._disconnect()
        pass


    def login(self) -> bool:
        """Sends login packet"""
        packet_id = random.randint(0, 2**31 - 1)
        self.socket.sendall(RCON._encode_packet(packet_id, 3, self.password))
        return self._receive_response(login_id=packet_id) == "Auth successful"
    

    def send(self, command: str) -> str:
        """
        Sends provided command to the RCON server. Calling this method
        before login will always result in an error being returned from
        the server.

        Args:
            command: RCON command to be executed.
        """
        packet_id = random.randint(0, 2**31 - 1)
        self.socket.sendall(RCON._encode_packet(packet_id, 2, command))
        # second packet with invalid type, to determine when fragmented
        # response packet ends 
        term_id = random.randint(0, 2**31 - 1)
        self.socket.sendall(RCON._encode_packet(term_id, 100, ""))
        return self._receive_response()
    

    def _receive_response(self, login_id: int | None = None) -> str:
        resp = ""
        while True:
            data = self.socket.recv(4096)
            if not data:
                break

            length, packet_id, packet_type, payload = RCON._decode_packet(data)
            if packet_id == -1:
                return "Auth failed"
            if login_id is not None and packet_id == login_id:
                return "Auth successful"
            if packet_type != 0 and login_id is None:
                break
            if "Unknown request" in payload:
                break

            resp += payload

        return resp


    def _connect(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
    
    
    def _disconnect(self) -> None:
        self.socket.close()


    @staticmethod
    def _encode_packet(id: int, type: int, payload: str) -> bytearray:
        # Structure: Length (4) | ID (4) | Type (4) | Payload (N) | \x00 | \x00

        payload_bytes = payload.encode("ascii")
        body = bytearray()
        body.extend(int.to_bytes(id, length=4, byteorder="little", signed=True))
        body.extend(int.to_bytes(type, length=4, byteorder="little", signed=True))
        body.extend(payload_bytes)
        body.extend(b"\x00\x00") # one for 
        
        data = bytearray()
        data.extend(int.to_bytes(len(body), length=4, byteorder="little", signed=True))
        data.extend(body)
        return data
    

    @staticmethod
    def _decode_packet(data: bytes) -> tuple[int, int, int, str]:
        # Structure: Length (4) | ID (4) | Type (4) | Payload (N) | \x00 | \x00

        length = int.from_bytes(data[:4], byteorder="little")
        packet_id = int.from_bytes(data[4:8], byteorder="little")
        packet_type = int.from_bytes(data[8:12], byteorder="little")
        # Payload starts at 12 and ends at length plus 4 bytes
        # (from leangth header) minus two null bytes
        payload = data[12:length+2].decode("ascii", errors="ignore")
        return length, packet_id, packet_type, payload
