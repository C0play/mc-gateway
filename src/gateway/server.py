import json
import socket
import select
import signal
import threading
from subprocess import CalledProcessError 

from ..utils.logger import logger
from ..packet.packet import Packet, Null, Status, Login
from .client import Client, State

from ..config.config import Config
from ..whitelist.manager import WhitelistManager
from ..session.manager import SessionManager



class Server:
    
    def __init__(self, config: Config, whitelist: WhitelistManager, sessions: SessionManager) -> None:
        try:
            self._shutdown = False
            
            self.config = config
            self._whitelist = whitelist
            
            self._sessions = sessions
            threading.Thread(target=sessions.autoshutdown, daemon=True).start()

            self._client_count_lock = threading.Lock()
            self._client_count = 0
            
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
    
    
    def start(self) -> 'Server':
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
            return self


    def _handle_ctrl_socket(self):
        control_sock, _ = self._ctrl_socket.accept()
        try:
            threading.Thread(target=self.handle_cmd, daemon=True, args=(control_sock,)).start()
        except Exception as e:
            logger.error(f"control socket: {e}")


    def _handle_mc_socket(self):
        client_sock, addr = self._server_socket.accept()
        client = Client(client_sock, addr)
        try:
            with self._client_count_lock:
                logger.info(f"new {client}, total: {self._client_count}")

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
        
        except Exception as e:
            logger.error(f"{client}: {e}")
        finally:
            client.close()
            

    def _process_handshake(self, client, handshake: Packet):
        try:
            subdomain, domain = handshake.data[3].split('.', 1)

            if not (self._whitelist.validate(subdomain=subdomain) and self.config.server.domain == domain):
                logger.info(f"{client} invalid domain: " + subdomain + "." + domain)
                return
            
            if len(handshake.data) < 2 or handshake.data[1] is not Null.serverbound.handshake:
                return
            
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
        except Exception as e:
            raise RuntimeError(f"status handshake: {e}")


    def _process_login(self, client, handshake):
        try:
            subdomain, domain = handshake.data[3].split('.', 1)

            login_start = Packet(client).read()

            logger.info(f"{client} {login_start.data}")

            if login_start.data[1] is Login.serverbound.login_start:
                username = login_start.data[2]

                if not self._whitelist.validate(username = username, subdomain = subdomain):
                    logger.warning(f"{client} unknown player tried logging in: {(username, login_start.data[3])}")
                    return
                
                try:
                    session = self._sessions.create(client, subdomain)
                    
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

                    self._sessions.delete(client)
                except:
                    logger.exception(f"failed to handle valid {client}")

        except NotImplementedError as e:
            logger.warning(f"{client} {e}")
        except (CalledProcessError) as e:
            logger.error(f"{client} subprocess command failed {e}")
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.warning(f"{client} disconnected during login")
        except Exception as e:
            raise RuntimeError(f"{client} login handshake: {e}")


    def handle_cmd(self, sock):
        response = {"status": "ERROR", "message": "unknown error"}
        cmd: list[str] = []
        try:
            data = sock.recv(1024).decode().strip()
            if not data:
                return
        
            cmd = data.split()

            if cmd[0] != "status":
                logger.info(f"handle_cmd received: {cmd}")
            
            if cmd[0] == "stop":
                self._shutdown = True
                response = Server._make_cmd_response("ERROR", "shutdown initiated")
                
            elif cmd[0] == "status":
                with self._client_count_lock:
                    response = Server._make_cmd_response("ERROR", self._client_count)
                        
            elif cmd[0] == "add-player":
                if len(cmd[1:]) != 2:
                    response = Server._make_cmd_response("ERROR", "usage: add-player <name> <server_subdomain>")
                else:
                    username, server_subdomain = cmd[1], cmd[2]
                    try:
                        self._whitelist.storage.create(username, server_subdomain)
                    except Exception as e:
                        response = Server._make_cmd_response("ERROR", f"player addition failed: {e}")
                    else:
                        response = Server._make_cmd_response("ERROR", f"player {username} added to {server_subdomain}")
                        
            elif cmd[0] == "remove-player":
                if len(cmd[1:]) != 2:
                    response = Server._make_cmd_response("ERROR", "usage: remove-player <name> <server_subdomain>")
                else:
                    username, server_subdomain = cmd[1], cmd[2]
                    try:
                        self._whitelist.storage.delete(username, server_subdomain)
                    except Exception as e:
                        response = Server._make_cmd_response("ERROR", f"player removal failed: {e}")
                    else:
                        response = Server._make_cmd_response("ERROR", f"player {username} removed from {server_subdomain}")
                        
            elif cmd[0] == "add-container":
                if len(cmd[1:]) != 2:
                    response = Server._make_cmd_response("ERROR", "usage: add-container <ip> <port>")
                else:
                    ip, port = cmd[1], cmd[2]
                    try:
                        server_subdomain = self._sessions.containers.storage.create(ip, int(port))
                    except Exception as e:
                        response = Server._make_cmd_response("ERROR", f"container addition failed: {e}")
                    else:
                        response = Server._make_cmd_response("ERROR", f"container {ip}:{port} received {server_subdomain}")
                        
            elif cmd[0] == "remove-container":
                if len(cmd[1:]) != 1:
                    response = Server._make_cmd_response("ERROR", "usage: remove-container <server_subdomain>")
                else:
                    server_subdomain = cmd[1]
                    try:
                        self._sessions.containers.storage.delete(server_subdomain)
                    except Exception as e:
                        response = Server._make_cmd_response("ERROR", f"container removal failed: {e}")
                    else:
                        response = Server._make_cmd_response("ERROR", f"container {server_subdomain} removed")
                        
            elif cmd[0] == "add-host":
                if len(cmd[1:]) != 4:
                    response = Server._make_cmd_response("ERROR", "usage: add-host <ip> <mac> <user> <path>")
                else:
                    ip, mac, user, path = cmd[1], cmd[2], cmd[3], cmd[4]
                    try:
                        self._sessions.containers.hostManager.storage.add(ip, mac, user, path)
                    except Exception as e:
                        response = Server._make_cmd_response("ERROR", f"host addition failed: {e}")
                    else:
                        response = Server._make_cmd_response("ERROR", f"added {ip} to hosts")

            elif cmd[0] == "remove-host":
                if len(cmd[1:]) != 1:
                    response = Server._make_cmd_response("ERROR", "usage: remove-host <ip>")
                else:
                    ip = cmd[1]
                    try:
                        self._sessions.containers.hostManager.storage.remove(ip)
                    except Exception as e:
                        response = Server._make_cmd_response("OK", f"host removal failed: {e}")
                    else:
                        response = Server._make_cmd_response("OK", f"{ip} removed")
                        
            elif cmd[0] == "list":
                response = {
                    "status": "OK", 
                    "players": self._whitelist.storage.dict(), 
                    "containers": self._sessions.containers.storage.dict(),
                    "hosts": self._sessions.containers.hostManager.storage.dict()
                }

            else:
                response = Server._make_cmd_response("ERROR", f"unknown command {cmd[0]}")

        except Exception as e:
            response = Server._make_cmd_response("ERROR", str(e))
        finally:
            try:
                if cmd[0] != "--status":
                    if response.get("status") == "OK":
                        logger.info(f"handle_cmd OK: {cmd}")
                    else:
                        logger.error(f"handle_cmd ERROR: {cmd} -> {response.get('message')}")
                
                sock.sendall(json.dumps(response).encode())
            except Exception:
                pass
            finally:
                sock.close()
    

    def _signal_handler(self, signum, _):
        logger.info(f"received: {signum}. Closing...")
        self._shutdown = True
        try:
            with socket.create_connection(("127.0.0.1", self.config.server.control_port), timeout=0.2) as s:
                s.sendall(b"stop")
        except Exception:
            pass


    @staticmethod
    def _make_cmd_response(status: str, message) -> dict[str, str]:
        return {"status": status, "message": str(message)}