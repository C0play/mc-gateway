import socket
import select
import signal
import uvicorn
import logging
import threading
from subprocess import CalledProcessError 

from ..utils.logger import logger
from ..packet.packet import Packet, Null, Status, Login

from ..config.config import Config
from ..whitelist.manager import WhitelistManager
from ..session.manager import SessionManager

from .client import Client, State
from .api import API



class Server:
    """
    The main server class that handles Minecraft client connections and control commands.
    """
    
    def __init__(self, config: Config, whitelist: WhitelistManager, sessions: SessionManager) -> None:
        """
        Initializes the Server with configuration, whitelist, and session managers.
        Sets up the Minecraft server socket and the control socket.

        Args:
            config: The configuration object.
            whitelist: The whitelist manager.
            sessions: The session manager.
        
        Raises:
            RuntimeError: If socket binding or initialization fails.
        """
        try:
            self._shutdown = False
            
            self.config = config
            self._whitelist = whitelist
            self._sessions = sessions
            
            self._client_count_lock = threading.Lock()
            self._client_count = 0
            
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

            try:
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._server_socket.bind((self.config.server.ip, self.config.server.port))
                self._server_socket.listen(self.config.server.max_clients)
            except Exception as e:
                raise RuntimeError(f"Minecraft socket: {e}")
            
            logger.info(f"server listening on {self.config.server.ip}:[mc:{self.config.server.port}, api:{self.config.server.control_port}]")
        
        except Exception as e:
            raise RuntimeError(f"Exception during server init: {e}")
    

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
                    self._handle_mc_socket()

        except Exception as e:
            logger.critical(f"server: {e}")
        finally:
            logger.info(f"cleaning resources")
            try:
                self._server_socket.close()
            except Exception as e:
                logger.error(f"closing mc_socket: {e}")
            logger.info("Server stopped")


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
            access_log=False 
        )


    def _handle_mc_socket(self):
        """Accepts a connection on the Minecraft socket, creates a Client instance and
        starts a thread to handle the connection.
        """

        client_sock, addr = self._server_socket.accept()
        client = Client(client_sock, addr)

        with self._client_count_lock:
            self._client_count += 1
            logger.info(f"new {client}, total: {self._client_count}")

        try:
            threading.Thread(target=self._handle_client, daemon=True, args=(client,)).start()
        except Exception as e:
            logger.error(f"client handling: {e}")


    def _handle_client(self, client: Client) -> None:
        try:
            handshake = Packet(client).read()
            self._process_handshake(client, handshake)
            
            if handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == State.Status:
                self._proces_status_req(client)
            elif handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == State.Login:
                self._handle_login(client, handshake)
            else:
                raise ValueError(f"")
            
        except (NotImplementedError, ConnectionError) as e:
            logger.warning(f"{client}: {e}")
        except Exception as e:
            logger.error(f"{client}: {e}")
        finally:
            client.close()
            with self._client_count_lock:
                self._client_count -= 1
            

    def _process_handshake(self, client: Client, handshake: Packet):
        try:
            subdomain, domain = handshake.data[3].split('.', 1)
            
            if not (self._whitelist.validate(subdomain=subdomain) and self.config.server.domain == domain):
                logger.info(f"{client} invalid domain: " + subdomain + "." + domain)
                return
            
            if len(handshake.data) < 2 or handshake.data[1] is not Null.serverbound.handshake:
                return
            
            client.subdomain = subdomain
            logger.info(f"{client} {handshake.data}")
                    
        except NotImplementedError as e:
            logger.warning(f"{client} {e}")
            return
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(f"{client} disconnected during handshake")
            return
        except Exception as e:
            raise RuntimeError(f"handshake: {e}")


    def _proces_status_req(self, client):
        try:
            status_req = Packet(client).read()
            
            logger.info(f"{client} {status_req.data}")
                
            if status_req.data[1] is Status.serverbound.status_request:
                status_req.respond()

                ping_req = Packet(client).read()
                logger.info(f"{client} {ping_req.data}")

                if ping_req.data[1] is Status.serverbound.ping_request:
                    ping_req.respond()

            
        except (ConnectionError, ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(f"{client} disconnected during status")
        except NotImplementedError as e:
            logger.warning(f"{client} {e}")
        except Exception as e:
            raise RuntimeError(f"status: {e}")


    def _handle_login(self, client: Client, handshake: Packet):
        try:
            subdomain, domain = handshake.data[3].split('.', 1)

            login_start = Packet(client).read()

            logger.info(f"{client} {login_start.data}")

            if login_start.data[1] is Login.serverbound.login_start:
                username = login_start.data[2]

                if not self._whitelist.validate(username = username, subdomain = subdomain):
                    logger.warning(f"{client} unknown player tried logging in: {(username, subdomain)}")
                    login_start.respond("You are not whitelisted.", "red")
                    return
                
                client.username = username
                self._handle_session(client, subdomain, handshake, login_start)


        except NotImplementedError as e:
            logger.warning(f"{client} {e}")
        except (CalledProcessError) as e:
            logger.error(f"{client} subprocess command failed {e}")
        except (ConnectionError, ConnectionResetError, BrokenPipeError) as e:
            logger.warning(f"{client} disconnected during login")
        except Exception as e:
            raise RuntimeError(f"{client} login: {e}")


    def _handle_session(self, client: Client, subdomain: str, handshake: Packet, login_start: Packet) -> None:
        
        try:
            session = self._sessions.open(client, subdomain)
        except (ValueError, KeyError) as e:
            logger.info(f"{client} denied connection: {e}")
            login_start.respond("Your server was deleted.", "red")
            return
        except Exception as e:
            logger.exception(f"failed to create session for {client}: {e}")
            return
        
        try:
            if session.container.is_online():
                logger.info(f"{client} container online, forwarding...")
                
                try:
                    session.forward(handshake, login_start)
                except:
                    login_start.respond("Can't connect to server.", "red")
                    logger.exception(f"{client} container connection failed (server starting?)")
            
            elif session.container.is_starting():
                login_start.respond("Server is starting, please wait.", "green")
                logger.info(f"{client} container start already in progress")
                return
            
            else:
                login_start.respond("Server is offline, starting.", "aqua")
                logger.info(f"{client} container offline, starting...")
                
                if session.container.start():
                    logger.info(f"{client} container online")
                else:
                    logger.error(f"{client} container start failed")
        except:
            logger.exception(f"failed to handle valid {client}")
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