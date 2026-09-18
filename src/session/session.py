import select
import socket
import time

from src.exceptions.errors import ServiceError

from ..container.container import BaseContainer
from ..gateway.client import Client
from ..protocol.protocol import BaseLoginPacket, HandshakePacket
from ..utils.logger import logger


class Session:
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

    def forward(self, handshake: HandshakePacket, login: BaseLoginPacket) -> None:
        """
        Forwards provided packets to the container, then loops to forward traffic bidirectionally.

        Args:
            handshake: Handshake packet with intent=login.
            login: Login packet.

        Raises:
            ServiceError: If connecting to the container fails after all attempts.
            ConnectionError: If connecting fails before all attempts are exhausted.
            ConnectionAbortedError: If the client disconnects before a connection is established.
            ValueError: If the container socket is None after connecting.
        """

        self._connect()
        if not self.container_socket:
            raise ValueError("socket was None when trying to forward")

        self.container_socket.sendall(handshake.reencode())
        self.container_socket.sendall(login.reencode())

        sess_start = time.monotonic()
        last_send = None
        total_rtt, rtt_samples = 0.0, 0

        kick_sent = False

        try:
            self.client.socket.setblocking(True)
            self.container_socket.setblocking(True)

            while True:
                rlist, _, _ = select.select(
                    [self.client.socket, self.container_socket], [], []
                )

                if self._server_disconnect_signal and not kick_sent:
                    kick_sent = True
                    self.container.send_command(
                        f"/kick {self.client.username} {self._server_disconnect_reason}"
                    )

                if self.client.socket in rlist:
                    self._transfer(
                        self.client.socket,
                        self.container_socket,
                        "disconnected during forwarding",
                    )
                    last_send = time.monotonic()

                elif self.container_socket in rlist:
                    self._transfer(
                        self.container_socket,
                        self.client.socket,
                        "container disconnected during forwarding",
                    )

                    if not last_send:
                        continue

                    total_rtt += time.monotonic() - last_send
                    rtt_samples += 1
                    last_send = None

        except StopIteration as e:
            logger.info(f"{self.client}: {e}")
        except Exception as e:
            raise ServiceError(f"forwarding error: {e}")
        finally:
            logger.info(f"{self.client}: forwarding done")

            try:
                self._disconnect()
            except ConnectionError as e:
                logger.error(
                    f"{self.client}: failed to disconnect container after forwarding: {e}"
                )

            if rtt_samples > 0:
                avg_ms = (total_rtt / rtt_samples) * 1000.0
                duration = time.monotonic() - sess_start
                logger.info(
                    f"{self.client}: avg ping {avg_ms:.2f} ms over {rtt_samples} samples (session {duration:.1f}s)"
                )

    def _connect(self) -> None:
        """
        Establishes connection to the container's socket.

        Raises:
            ConnectionAbortedError: If the client disconnects while waiting.
            ConnectionError: If host/container is offline, retries are exhausted,
                or a transport error occurs.
            ServiceError: If the connection to the server fails.
        """
        if not self.container.host.is_online():
            raise ConnectionError("can not connect if host is offline")

        if not self.container.is_online():
            raise ConnectionError("can not connect if container is offline")

        attempts, wait_time = 3, 1
        for attempt in range(attempts):
            if self._client_disconnected(wait_time):
                raise ConnectionAbortedError("client disconnected")
            wait_time = 10

            try:
                self.container_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM
                )
                self.container_socket.connect(
                    (self.container.host.ip, self.container.mc_port)
                )

                logger.info(
                    f"{self.client}: connection attempt {attempt + 1} to {self.container.subdomain} suceeded"
                )
                return
            except (ConnectionRefusedError, OSError) as e:
                self._disconnect()
                logger.warning(
                    f"{self.client}: connection attempt {attempt + 1} to {self.container} failed, retrying in {wait_time}s: {e}"
                )

        raise ServiceError(f"failed to connect after {attempts} attempts")

    def _transfer(
        self, source: socket.socket, destination: socket.socket, error_msg: str
    ) -> None:
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
            data = source.recv(4096)
        except (BlockingIOError, OSError):
            data = None

        if not data:  # source closed
            raise StopIteration(error_msg)

        try:
            destination.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError) as _:
            raise StopIteration(error_msg)

    def _disconnect(self) -> None:
        """
        Closes the container's socket.

        Raises:
            ConnectionError: If closing the socket fails.
        """
        try:
            if not self.container_socket:
                return
            self.container_socket.close()
        except Exception as e:
            raise ConnectionError(f"failed to close the connection: {e}")

    def _client_disconnected(self, timeout: float = 0.0) -> bool:
        """
        Checks if the client socket is closed or has data ready to peek (indicating potential closure).

        Args:
            timeout: How long to wait for the socket.

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
