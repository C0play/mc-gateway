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

        last_client_send: float | None = None
        rtt_sum = 0.0
        rtt_count = 0
        sess_start = time.monotonic()

        try:
            self.client.socket.setblocking(True)
            self.container_socket.setblocking(True)
            while True:
                rlist, _, _ = select.select([self.client.socket, self.container_socket], [], [])
                for sock in rlist:
                    if sock is self.client.socket:
                        data = None
                        try:
                            data = self.client.socket.recv(65536)
                        except (BlockingIOError, OSError):
                            data = None
                        if not data: # client closed
                            return 
                        
                        try:
                            self.container_socket.sendall(data)
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            logger.error(f"{self.client} container disconnected during forwarding")
                            return

                        last_client_send = time.monotonic()

                    else:
                        data = None
                        try:
                            data = self.container_socket.recv(65536)
                        except (BlockingIOError, OSError):
                            data = None
                        if not data: # container closed
                            logger.error(f"{self.client} container disconnected during forwarding")
                            return
                        
                        try:
                            self.client.socket.sendall(data)
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            logger.info(f"{self.client} client disconnected during forwarding")
                            return
                        
                        if last_client_send is not None:
                            rtt = (time.monotonic() - last_client_send)
                            if rtt >= 0:
                                rtt_sum += rtt
                                rtt_count += 1
                            last_client_send = None
                        
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.error(f"{self.client} connection closed unexpectedly {e}")
        except Exception as e:
            logger.error(f"{self.client} forwarding error: {e}")
        finally:
            logger.info(f"{self.client} forwarding done")
            try:
                self._disconnect()
            except Exception as e:
                logger.error(f"failed to disconnect container, after forwarding: {e}")
            
            try:
                if rtt_count > 0:
                    avg_ms = (rtt_sum / rtt_count) * 1000.0
                    duration = time.monotonic() - sess_start
                    logger.info(f"{self.client}: avg ping {avg_ms:.2f} ms over {rtt_count} samples (session {duration:.1f}s)")
            except Exception:
                pass


    def _connect(self) -> None:
        """Create a connection to the container's port"""
        try:
        
            if not self.container.host.is_online():
                raise RuntimeError(f"can not connect if host is offline")
            
            if not self.container.is_online():
                raise RuntimeError(f"can not connect if container is offline")
        
            attempts, wait_time = 3, 10
            for attempt in range(attempts):
                if self._client_disconnected(0.0):
                    raise RuntimeError("client disconnected")
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
            if self.client.socket in rlist:
                try:
                    peek = self.client.socket.recv(1, socket.MSG_PEEK)
                except (BlockingIOError, OSError):
                    return False
                return peek == b""
            return False
        except Exception:
            return True