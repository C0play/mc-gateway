import logging
import select
import signal
import socket
import threading

import uvicorn

from ..api.api import API
from ..config.config import Config
from ..exceptions.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceError,
)
from ..protocol.factory import ProtocolFactory
from ..protocol.types import Intent
from ..session.manager import SessionManager
from ..utils.logger import logger
from ..whitelist.manager import WhitelistManager
from .client import Client


class Server:
    """
    The main server class that handles Minecraft client connections and control commands.
    """

    def __init__(
        self,
        config: Config,
        whitelist: WhitelistManager,
        sessions: SessionManager,
    ) -> None:
        """
        Initializes the Server with configuration, whitelist, and session managers.
        Sets up the Minecraft server socket and the control socket.

        Args:
            config: The configuration object.
            whitelist: The whitelist manager.
            sessions: The session manager.

        Raises:
            ServiceError: If socket binding or initialization fails.
        """
        self._shutdown = False

        self.config = config
        self._whitelist = whitelist
        self._sessions = sessions
        self._protocols = ProtocolFactory()

        self._client_count_lock = threading.Lock()
        self._client_count = 0

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.config.server.ip, self.config.server.port))
        self._server_socket.listen(self.config.server.max_clients)

        logger.info(
            f"SERVER: listening on {self.config.server.ip}:[mc:{self.config.server.port}, api:{self.config.server.control_port}]"
        )

    def start(self) -> None:
        """
        Starts the main server loop, listening for incoming connections on both sockets.
        Handles graceful shutdown on signals.
        """
        try:
            threading.Thread(target=self._sessions.autoshutdown, daemon=True).start()
            threading.Thread(target=self._run_api, daemon=True).start()

            while not self._shutdown:
                sockets = [self._server_socket]
                readyl, _, _ = select.select(sockets, [], [], 1.0)

                if self._server_socket in readyl and not self._shutdown:
                    threading.Thread(target=self._handle_mc_socket, daemon=True).start()

        except Exception:
            logger.exception("SERVER: unexpected error")
        finally:
            logger.info("SERVER: cleaning resources")
            self._server_socket.close()
            logger.info("SERVER: stopped")

    def _run_api(self):
        """Runs the uvicorn API server in a thread with custom logging configuration."""

        # Disable all uvicorn loggers
        for log_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            log = logging.getLogger(log_name)
            log.disabled = True

        uvicorn.run(
            API(self).app,
            host=self.config.server.ip,
            port=self.config.server.control_port,
            log_config=None,
            access_log=False,
        )

    def _handle_mc_socket(self):
        """Accepts a connection on the Minecraft socket and creates a Client instance to handle it."""

        with self._client_count_lock:
            self._client_count += 1

        client = None
        try:
            client_sock, addr = self._server_socket.accept()
            client = Client(client_sock, addr)

            protocol = self._protocols.get(client_sock)
            client.set_protocol(protocol)

            self._process_handshake(client)

        except (BadRequestError, NotImplementedError) as e:
            logger.info(f"{client}: {e}")
        except (ConnectionError, ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(f"{client}: {e}")
        except Exception:
            logger.exception(f"{client}: unexpected error")
        finally:
            if client is not None:
                client.close()
            with self._client_count_lock:
                self._client_count -= 1

    def _process_handshake(self, client: Client) -> None:
        subdomain, domain = client.packets.handshake.data.address.split(".", 1)

        if not (
            self._whitelist.validate(subdomain=subdomain)
            and self.config.server.domain == domain
        ):
            logger.debug(f"invalid domain: registered domain={domain}")
            raise BadRequestError("invalid domain: " + subdomain + "." + domain)

        client.subdomain = subdomain
        logger.info(f"{client} {client.packets.handshake.data}")

        if client.packets.handshake.data.intent == Intent.Status:
            self._proces_status_req(client)
        elif client.packets.handshake.data.intent == Intent.Login:
            self._handle_login(client)
        else:
            raise BadRequestError(
                f"unsupported intent: {client.packets.handshake.data.intent}"
            )

    def _proces_status_req(self, client: Client):
        client.packets.status.read()
        logger.info(f"{client} {client.packets.status.data}")

        container = self._sessions.containers.storage.read(
            allow_empty=False, subdomain=client.subdomain
        )
        game = container[0].config["version"]
        proto = client.packets.handshake.data.version

        client.packets.status.respond(game, proto)

        client.packets.ping.read()
        logger.info(f"{client} {client.packets.ping.data}")
        client.packets.ping.respond()

    def _handle_login(self, client: Client):
        client.packets.login.read()
        client.username = client.packets.login.data.name

        logger.info(f"{client}: {client.packets.login.data}")

        if not self._whitelist.validate(
            username=client.packets.login.data.name, subdomain=client.subdomain
        ):
            client.packets.login.respond("You are not whitelisted.", "red")
            raise BadRequestError("unknown player")

        self._handle_session(client)

    def _handle_session(self, client: Client) -> None:

        try:
            session = self._sessions.open(client)
        except (ConflictError, NotFoundError) as e:
            logger.warning(f"{client}: refused to create session: {e}")
            client.packets.login.respond("Can't connect to server.", "red")
            return
        except ValueError as e:
            logger.info(f"{client}: refused to create session: {e}")
            return
        except ServiceError:
            logger.exception(f"{client}: failed to create session")
            return

        try:
            if session.container.is_online():
                logger.info(f"{client} container online, forwarding...")
                try:
                    session.forward(client.packets.handshake, client.packets.login)
                except ConnectionAbortedError as e:
                    logger.info(f"{client}: disconnected before forwarding: {e}")
                except (ConnectionError, ValueError, ServiceError) as e:
                    logger.error(f"{client}: container connection failed {e}")
                    client.packets.login.respond("Can't connect to server.", "red")

            elif session.container.is_starting():
                client.packets.login.respond(
                    "Server is starting, please wait.", "green"
                )
                logger.info(f"{client}: container starting")
                return

            else:
                client.packets.login.respond("Server is offline, starting.", "aqua")
                logger.info(f"{client}: container offline, starting...")

                try:
                    session.container.start()
                    logger.info(f"{client}: container online")
                except TimeoutError as e:
                    self._sessions.containers.unload(session.container.subdomain)
                    logger.error(f"{client}: container start timed out: {e}")

        finally:
            self._sessions.close(client)

    def get_client_count(self) -> int:
        with self._client_count_lock:
            return self._client_count

    def _init_shutdown(self, reason: str) -> None:
        self._shutdown = True
        logger.info(f"shutting down: {reason}")

    def _signal_handler(self, signum, _):
        self._init_shutdown(f"received: {signum}")
