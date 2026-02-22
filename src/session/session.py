import time
import socket
import select

from ..gateway.client import Client
from ..container.container import BaseContainer
from ..packet.packet import Packet
from ..utils.logger import logger


class Session():
    """
    Represents an active bi-directional forwarding session between a client and a container.
    """
    
    def __init__(self, client: Client, container: BaseContainer) -> None:
        """
        Initializes the session.

        Args:
            client: The connected client.
            container: The target container.
        """
        self.client = client
        self.container = container
        self.container_socket = None
        self._server_disconnect_signal = False
        self._server_disconnect_reason = ""
    

    def forward(self, *packets: Packet) -> None:
        """
        Forwards provided packets to the container, then loops to forward traffic bidirectionally.
        
        Args:
            *packets: Initial packets to send to the container (e.g. handshake, login).
        """
        try:
            self._connect()
        except Exception as e:
            logger.error(f"failed to connect to container, before forwarding: {e}")
            return
        
        if not self.container_socket:
            logger.error(f"container socket of {self.container} was None when trying to forward")
            return

        for packet in packets:
            self.container_socket.sendall(packet.reencode())

        sess_start = time.monotonic()
        last_send = None
        total_rtt, rtt_samples = 0.0, 0

        try:
            self.client.socket.setblocking(True)
            self.container_socket.setblocking(True)

            while True and not self._server_disconnect_signal:
                rlist, _, _ = select.select([self.client.socket, self.container_socket], [], [])
                
                if self.client.socket in rlist:
                    self._transfer(self.client.socket, self.container_socket, "disconnected during forwarding")
                    last_send = time.monotonic()

                elif self.container_socket in rlist:
                    self._transfer(self.container_socket, self.client.socket, "container disconnected during forwarding")
                    
                    if not last_send: 
                        continue
                    
                    total_rtt += time.monotonic() - last_send
                    rtt_samples += 1
                    last_send = None

        except StopIteration as e:
            logger.warning(e)
        except Exception as e:
            logger.error(f"{self.client} forwarding error: {e}")
        finally:
            logger.info(f"{self.client} forwarding done")

            try:
                self._disconnect()
            except Exception as e:
                logger.error(f"failed to disconnect container, after forwarding: {e}")
            
            if rtt_samples > 0:
                avg_ms = (total_rtt / rtt_samples) * 1000.0
                duration = time.monotonic() - sess_start
                logger.info(f"{self.client}: avg ping {avg_ms:.2f} ms over {rtt_samples} samples (session {duration:.1f}s)")


    def _transfer(self, source: socket.socket, destination: socket.socket, error_msg: str) -> None:
        """
        Transfers a portion of data from source to destination.

        Args:
            source: The socket to read from.
            destination: The socket to write to.
            error_msg: The error message to use if transfer fails.
            
        Raises:
             StopIteration: If the source socket is closed or an error occurs.
        """
        try:
            data = source.recv(65536)
        except (BlockingIOError, OSError):
            data = None
        if not data: # source closed
            raise StopIteration(f"{self.client} {error_msg}")
        
        try:
            destination.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            raise StopIteration(f"{self.client} {error_msg}")


    def _connect(self) -> None:
        """
        Establishes connection to the container's socket.
        Retries up to 3 times if connection is refused.
        
        Raises:
             RuntimeError: If connection fails after retries or if host/container is offline.
             ConnectionAbortedError: If the client disconnects while waiting.
        """
        try:
        
            if not self.container.host.is_online():
                raise RuntimeError(f"can not connect if host is offline")
            
            if not self.container.is_online():
                raise RuntimeError(f"can not connect if container is offline")
        
            attempts, wait_time = 3, 10
            for attempt in range(attempts):
                if self._client_disconnected(0.0):
                    raise ConnectionAbortedError("client disconnected")

                try:
                    self.container_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.container_socket.connect((self.container.host.ip, self.container.port))
                    
                    logger.info(f"{self.client} connected to {self.container.subdomain} on attempt {attempt + 1}")
                    return
                
                except (ConnectionRefusedError, OSError) as e:
                    self._disconnect()
                    logger.warning(f"{self.client} connection to {self.container} attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    if self._client_disconnected(wait_time):
                        raise RuntimeError("client disconnected")

            raise RuntimeError(f"connect failed after {attempts} attempts")
        except Exception as e:                
            raise RuntimeError(f"failed to connect: {e}")


    def _disconnect(self) -> None:
        """
        Closes the container's socket.
        
        Raises:
             RuntimeError: If closing the socket fails.
        """
        try:
            if not self.container_socket:
                return
            self.container_socket.close()
        except Exception as e:
            raise RuntimeError(f"failed to close the connection: {e}")
        

    def _client_disconnected(self, timeout: float = 0.0) -> bool:
        """
        Checks if the client socket is closed or has data ready to peek (indicating potential closure).
        
        Args:
            timeout: How long to wait for checking socket state.
            
        Returns:
            bool: True if the client appears disconnected, False otherwise.
        """
        try:
            rlist, _, _ = select.select([self.client.socket], [], [], timeout)
            if self.client.socket not in rlist:
                return False
        
            try:
                peek = self.client.socket.recv(1, socket.MSG_PEEK)
            except (BlockingIOError, OSError):
                return False
        
            return peek == b""
        
        except Exception:
            return True
        

    def server_disconnect(self, reason: str) -> None:
        """
        Signals that the session should end due to a server-side reason.
        
        Args:
            reason: The reason for disconnection.
        """
        self._server_disconnect_signal = True
        self._server_disconnect_reason = reason


    def dict(self) -> dict[str, str]:
        return {
            "client": str(self.client),
            "container": str(self.container),
        }

