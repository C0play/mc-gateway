import time
import socket
import select

from ..gateway.client import Client
from ..container.container import BaseContainer
from ..packet.packet import Packet
from ..utils.logger import logger


class Session():
    
    def __init__(self, client: Client, container: BaseContainer) -> None:
        self.client = client
        self.container = container
        self.container_socket = None
        self._server_disconnect_signal = False
        self._server_disconnect_reason = ""
    

    def forward(self, *packets: Packet) -> None:
        """Forward all provided packets to the container, and then all traffic between the client and the container."""
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
        """Connect the container's socket"""
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
        """Disconnect the container's socket"""
        try:
            if not self.container_socket:
                return
            self.container_socket.close()
        except Exception as e:
            raise RuntimeError(f"failed to close the connection: {e}")
        

    def _client_disconnected(self, timeout: float = 0.0) -> bool:
        """Return True if the client socket appears closed within timeout seconds.
        Any unexpected error is treated as disconnected.
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
        self._server_disconnect_signal = True
        self._server_disconnect_reason = reason

