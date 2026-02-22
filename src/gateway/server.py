import socket
import select
import signal
import threading
from subprocess import CalledProcessError 

from ..utils.logger import logger
from ..packet.packet import Packet, Null, Status, Login

from ..config.config import Config
from ..whitelist.manager import WhitelistManager
from ..session.manager import SessionManager

from .client import Client, State
from .api import API, TCPAdapter



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
            threading.Thread(target=sessions.autoshutdown, daemon=True).start()

            self._client_count_lock = threading.Lock()
            self._client_count = 0
            
            self.api = API(self)
            self.cmd_handler = TCPAdapter(self.api)

            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

            try:
                # minecraft socket
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._server_socket.bind((self.config.server.ip, self.config.server.port))
                self._server_socket.listen(self.config.server.max_clients)
            except Exception as e:
                raise RuntimeError(f"Minecraft socket: {e}")
            try:
                # control socket
                self._ctrl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._ctrl_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._ctrl_socket.bind((self.config.server.ip, self.config.server.control_port))
                self._ctrl_socket.listen(1)
            except Exception as e:
                raise RuntimeError(f"Control socket: {e}")
            
            logger.info(f"server listening at {self.config.server.ip}:{{mc:{self.config.server.port}, ctrl:{self.config.server.control_port}}}")
        
        except Exception as e:
            raise RuntimeError(f"Exception during server init: {e}")
    
    
    def start(self) -> None:
        """
        Starts the main server loop, listening for incoming connections on both sockets.
        Handles graceful shutdown on signals.
        """
        try:
            while not self._shutdown:
                sockets = [self._server_socket, self._ctrl_socket]
                readyl, _, _ = select.select(sockets, [], [])

                if self._ctrl_socket in readyl:
                    self._handle_ctrl_socket()                    
                elif self._server_socket in readyl and not self._shutdown:
                    self._handle_mc_socket()

        except Exception as e:
            logger.critical(f"server: {e}")
        finally:
            logger.info(f"cleaning resources")
            try:
                self._ctrl_socket.close()
            except Exception as e:
                logger.error(f"closing ctrl_socket: {e}")
            try:
                self._server_socket.close()
            except Exception as e:
                logger.error(f"closing mc_socket: {e}")
            logger.info("Server stopped")


    def _handle_ctrl_socket(self):
        """Accepts a connection on the control socket and starts a thread to handle commands."""
        
        control_sock, _ = self._ctrl_socket.accept()
        try:
            threading.Thread(target=self.cmd_handler.handle, daemon=True, args=(control_sock,)).start()
        except Exception as e:
            logger.error(f"control socket: {e}")


    def _handle_mc_socket(self):
        """Accepts a connection on the Minecraft socket, initializes a Client instance and
        starts a thread to handle the connection.
        """

        client_sock, addr = self._server_socket.accept()
        client = Client(client_sock, addr)

        with self._client_count_lock:
            self._client_count += 1
            logger.info(f"new {client}, total: {self._client_count}")

        try:
            threading.Thread(target=self.handle_client, daemon=True, args=(client,)).start()
        except Exception as e:
            logger.error(f"client handling: {e}")


    def handle_client(self, client: Client) -> None:
        try:
            handshake = Packet(client).read()
            self._process_handshake(client, handshake)
            
            if handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == State.Status:
                self._proces_status_req(client)
            elif handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == State.Login:
                self._process_login(client, handshake)
            else:
                raise ValueError(f"")
            
        except NotImplementedError as e:
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

            
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(f"{client} disconnected during status")
        except NotImplementedError as e:
            logger.warning(f"{client} {e}")
        except Exception as e:
            raise RuntimeError(f"status: {e}")


    def _process_login(self, client: Client, handshake: Packet):
        try:
            subdomain, domain = handshake.data[3].split('.', 1)

            login_start = Packet(client).read()

            logger.info(f"{client} {login_start.data}")

            if login_start.data[1] is Login.serverbound.login_start:
                username = login_start.data[2]

                if not self._whitelist.validate(username = username, subdomain = subdomain):
                    logger.warning(f"{client} unknown player tried logging in: {(username, login_start.data[3])}")
                    return
                
                client.username = username
                self._handle_session(client, subdomain, handshake, login_start)


        except NotImplementedError as e:
            logger.warning(f"{client} {e}")
        except (CalledProcessError) as e:
            logger.error(f"{client} subprocess command failed {e}")
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.warning(f"{client} disconnected during login")
        except Exception as e:
            raise RuntimeError(f"{client} login: {e}")


    def _handle_session(self, client: Client, subdomain: str, handshake: Packet, login_start: Packet) -> None:
        
        try:
            session = self._sessions.open(client, subdomain)
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


    def _signal_handler(self, signum, _):
        logger.info(f"received: {signum}. Closing...")
        self._shutdown = True
        try:
            with socket.create_connection(("127.0.0.1", self.config.server.control_port), timeout=0.2) as s:
                s.sendall(b"stop")
        except Exception:
            pass