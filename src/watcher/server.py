import os
import csv
import json
import time
import socket
import select
import signal
import threading
from dotenv import load_dotenv
from subprocess import CalledProcessError 
from ..packet.packet import Packet, Null, Status, Login
from .client import Client, state
from .backend import BackendPool


class Server:
    
    _config_loaded: bool = False

    _server_ip: str
    _server_port: int
    _ctrl_port: int
    _server_domain: str
    _server_max_clients: int
    
    _backend_pool: BackendPool

    @classmethod
    def load_config(cls, hosts_file_name: str, whitelist_file_name: str):
        if cls._config_loaded:
            return
        cls._config_loaded = True
        try:
            cls._server_ip = os.getenv("SERVER_IP", "0.0.0.0")
            cls._server_port = int(os.getenv("SERVER_PORT", "25567"))
            cls._ctrl_port = int(os.getenv("CTRL_PORT", "25566"))
            cls._server_domain = os.getenv("DOMAIN", "")
            cls._server_max_clients = int(os.getenv("CLIENTS", "4"))
            
            cls._backend_pool = BackendPool(hosts_file_name)
            Client.load_config(whitelist_file_name)
            
        except Exception as e:
            raise RuntimeError(f"exception during server config: {e}")


    def __init__(self) -> None:
        try:
            Server.load_config("hosts.csv", "allow_list.csv")
            
            self._shutdown = False
            
            self._client_count_lock = threading.Lock()
            self._client_count = 0
            
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

            threading.Thread(target=Server._backend_pool.cleanup_idle, daemon=True).start()

            try:
                # minecraft socket
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._server_socket.bind((Server._server_ip, Server._server_port))
                self._server_socket.listen(Server._server_max_clients)
            except Exception as e:
                raise RuntimeError(f"Minecraft socket: {e}")
            try:
                # control socket
                self._ctrl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._ctrl_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._ctrl_socket.bind((Server._server_ip, Server._ctrl_port))
                self._ctrl_socket.listen(1)
            except Exception as e:
                raise RuntimeError(f"Control socket: {e}")
            print(f"LOG: server listening at {Server._server_ip}:{Server._server_port}, ctrl {Server._ctrl_port}")
        except Exception as e:
            raise RuntimeError(f"Exception during server init: {e}")
    
    
    def start(self) -> None:
        try:
            while not self._shutdown:
                sockets = [self._server_socket, self._ctrl_socket]
                readyl, _, _ = select.select(sockets, [], [])

                if self._ctrl_socket in readyl:
                    control_sock, _ = self._ctrl_socket.accept()
                    try:
                        threading.Thread(target=self.handle_cmd, daemon=True, args=(control_sock,)).start()
                    except Exception as e:
                        print(f"ERROR: control socket: {e}")
                    
                elif self._server_socket in readyl and not self._shutdown:
                    client_sock, addr = self._server_socket.accept()
                    client = Client(client_sock, addr)
                    try:
                        with self._client_count_lock:
                            print(f"LOG: new {client}, total: {self._client_count}")

                        threading.Thread(target=self._handle_client, daemon=True, args=(client,)).start()
                    except Exception as e:
                        print(f"ERROR: client handling: {e}")

        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            print(f"LOG: cleaning resources")
            try:
                self._ctrl_socket.close()
            except Exception as e:
                print(f"ERROR: closing ctrl_socket:  {e}")
            try:
                self._server_socket.close()
            except Exception as e:
                print(f"ERROR: closing mc_socket:  {e}")
            print("LOG: Server stopped")


    def _handle_client(self, client: Client) -> None:
        try:
            try:
                handshake = Packet(client).read()

                if handshake.data[3] != Server._server_domain:
                    return
                if len(handshake.data) < 2:
                    return
                if not handshake.data[1] is Null.serverbound.handshake:
                    return
                
                print(f"LOG: {client} {handshake.data}")
                        
            except NotImplementedError as e:
                print(f"WARN: {client} {e}")
                return
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                print(f"LOG: {client} disconnected during handshake")
                return
            except Exception as e:
                raise RuntimeError(f"handshake: {e}")
            
            try:
                # If the first packet was a status handshake, then the client will immedietly send a status request
                if handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == state.Status:
                    status_req = Packet(client).read()
                    print(f"LOG: {client} {status_req.data}")
                        
                    if status_req.data[1] is Status.serverbound.status_request:
                        status_req.respond()

                        ping_req = Packet(client).read()
                        print(f"LOG: {client} {ping_req.data}")

                        if ping_req.data[1] is Status.serverbound.ping_request:
                            ping_req.respond()

                    return
                
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                print(f"LOG: {client} disconnected during status")
                return
            except Exception as e:
                raise RuntimeError(f"status handshake: {e}")
            
            try:
                # If the first packet was a login handshake, then the client will immedietly send a start_login
                if handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == state.Login:
                    login_start = Packet(client).read()
                    print(f"LOG: {client} {login_start.data}")

                    if login_start.data[1] is Login.serverbound.login_start:
                        username = login_start.data[2]
                        ip, port = Client.validate(username)
                        
                        if not ip or not port: 
                            print(f"LOG: {client} unknown player tried logging in: {(username, login_start.data[3])}")
                            return
                        
                        backend = Server._backend_pool.get(ip, port)

                        if backend.is_online():
                            print(f"LOG: {client} backend online, forwarding...")
                            try:
                                backend.connect()

                                handshake.forward(backend)
                                login_start.forward(backend)
                                
                                self._forward(client, backend)
                            except Exception as e:
                                print(f"LOG: {client} backend connection failed (server starting?): {e}")
                                login_start.respond("Can't connect to server.", "red")
                        else:
                            print(f"LOG: {client} backend offline, starting...")
                            
                            if backend.is_starting():
                                login_start.respond("Server is starting, please wait.", "green")
                                print(f"LOG: {client} backend start already in progress")
                                return
                            
                            login_start.respond("Server is offline, starting.", "aqua")
                            
                            try:
                                if backend.start():
                                    print(f"LOG: {client} backend online")
                                else:
                                    print(f"LOG: {client} backend start failed")
                            except Exception as e:
                                print(f"ERROR: {client} backend container start: {e}")
            
            except NotImplementedError as e:
                print(f"WARN: {client} {e}")
            except (CalledProcessError) as e:
                print(f"ERROR: {client} subprocess command failed {e}")
            except (ConnectionResetError, BrokenPipeError) as e:
                print(f"LOG: {client} disconnected during login")
            except Exception as e:
                raise RuntimeError(f"login handshake: {e}")
        except Exception as e:
            print(f"ERROR: {client}: {e}")
        finally:
            client.close()


    def _forward(self, client: Client, backend) -> None:
        Server._backend_pool.update_timestamp(backend.container.host.ip, backend.container.port)
        with self._client_count_lock:
            self._client_count += 1

        last_client_send: float | None = None
        rtt_sum = 0.0
        rtt_count = 0
        sess_start = time.monotonic()
        try:
            client.socket.setblocking(True)
            backend.socket.setblocking(True)
            while True:
                rlist, _, _ = select.select([client.socket, backend.socket], [], [])
                for sock in rlist:
                    if sock is client.socket:
                        data = None
                        try:
                            data = client.socket.recv(65536)
                        except (BlockingIOError, OSError):
                            data = None
                        if not data: # client closed
                            return 
                        try:
                            backend.socket.sendall(data)
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            print(f"LOG: {client} backend disconnected during forward")
                            return
                        last_client_send = time.monotonic()

                        Server._backend_pool.update_timestamp(backend.container.host.ip, backend.container.port)

                    else:
                        data = None
                        try:
                            data = backend.socket.recv(65536)
                        except (BlockingIOError, OSError):
                            data = None
                        if not data: # backend closed
                            print(f"LOG: {client} backend disconnected during forward")
                            return
                        if last_client_send is not None:
                            try:
                                if rtt := (time.monotonic() - last_client_send) >= 0:
                                    rtt_sum += rtt
                                    rtt_count += 1
                            except Exception:
                                pass
                            finally:
                                last_client_send = None
                        try:
                            client.socket.sendall(data)
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            print(f"LOG: {client} client disconnected during forward")
                            return
                        
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            print(f"LOG: {client} connection closed unexpectedly")
        except Exception as e:
            print(f"ERROR: {client} forwarding error: {e}")
        finally:
            print(f"LOG: forwarding done {client}")
            with self._client_count_lock:
                self._client_count -= 1
            try:
                if rtt_count > 0:
                    avg_ms = (rtt_sum / rtt_count) * 1000.0
                    duration = time.monotonic() - sess_start
                    print(f"LOG: {client}: avg ping {avg_ms:.2f} ms over {rtt_count} samples (session {duration:.1f}s)")
            except Exception:
                pass

                
    def handle_cmd(self, sock):
        response = {"status": "ERROR", "message": "unknown error"}
        try:
            data = sock.recv(1024).decode().strip()
            if not data:
                return
        
            cmd = data.split()
            
            if cmd[0] == "--stop":
                self._shutdown = True
                response = {"status": "OK", "message": "shutdown initiated"}
            elif cmd[0] == "--status":
                with self._client_count_lock:
                    response = {"status": "OK", "clients": self._client_count}
                        
            elif cmd[0] == "--addp":
                if len(cmd[1:]) < 3:
                    response = {"status": "ERROR", "message": "usage: --addp <name> <host_ip> <container_port>"}
                else:
                    name, ip, port = cmd[1], cmd[2], cmd[3]
                    if Client.whitelist.add(name, ip, port):
                        response = {"status": "OK", "message": f"player {name} added"}
                    else:
                        response = {"status": "ERROR", "message": f"addition failed"}
            elif cmd[0] == "--removep":
                if len(cmd[1:]) < 2:
                    response = {"status": "ERROR", "message": "usage: --removep <name>"}
                else:
                    name = cmd[1]
                    if Client.whitelist.remove(name):
                        response = {"status": "OK", "message": f"player {name} removed"}
                    else:
                        response = {"status": "ERROR", "message": f"removal failed, file not changed"}
            elif cmd[0] == "--list":
                response = {"status": "OK", "players": Client.whitelist.to_dict()}
                
            else:
                response = {"status": "ERROR", "message": f"unknown command {cmd[0]}"}

        except Exception as e:
            response = {"status": "ERROR", "message": str(e)}
        finally:
            try:
                sock.sendall(json.dumps(response).encode())
            except Exception:
                pass
            finally:
                sock.close()
    

    @classmethod
    def send_cmd(cls, cmds: list[str]) -> int:
        try:
            if len(cmds) <= 1:
                print("Usage: python server.py [--stop|--status|--addp <name> <uuid>|--list]")
                return 0
            
            load_dotenv()
            ctrl_port = int(os.getenv("CTRL_PORT", "25566"))

            with socket.create_connection(("127.0.0.1", ctrl_port), timeout=3.0) as s:
                cmd = ' '.join(cmds[1:])
                s.sendall(cmd.encode())

                response_data = s.recv(4096).decode()
                response = json.loads(response_data)
                
                if response["status"] == "OK":
                    if "message" in response:
                        print(f"SUCCESS: {response['message']}")
                    if "clients" in response:
                        print(f"Clients: {response['clients']}")
                    if "backends" in response:
                        print(f"Backends: {response['backends']}")
                    if "backend_host_status" in response:
                        print(f"Backend host online: {response['backend_host_status']}")
                    if "players" in response:
                        print("Whitelist:")
                        for username, info in response['players'].items():
                            print(f"  {username}: {info['ip']}:{info['port']}")
                    return 0
                else:
                    print(f"ERROR: {response['message']}")
                    return 1
            return 0
        except (ConnectionRefusedError, TimeoutError):
            print("ERROR: server is not running or not accessible")
            return 1
        except json.JSONDecodeError:
            print("ERROR: invalid response from server")
            return 1
        except Exception as e:
            print(f"ERROR: {e}")
            return 1
        

    def _signal_handler(self, signum, _):
        print(f"LOG: received: {signum}. Closing...")
        self._shutdown = True
        try:
            with socket.create_connection(("127.0.0.1", Server._ctrl_port), timeout=0.2) as s:
                s.sendall(b"--stop")
        except Exception:
            pass