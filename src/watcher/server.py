import re
import sys
import time
import socket
import select
from dotenv import dotenv_values

from ..packet.packet import Packet
from ..packet.packet import Null
from ..packet.packet import Status 
from ..packet.packet import Login

from .client import Client
from .client import state as state

from .backend import Backend

class Server:

    _allowed_ips = []

    try:
        _config = dotenv_values(".env")
            
        _server_ip = _config["SERVER_IP"]
        _server_port = int(_config["SERVER_PORT"] or 25567)
        _server_max_clients = int(_config["CLIENTS"] or "4" )

        _ctrl_port = int(_config["CTRL_PORT"] or 25566)

    except Exception as e:
        raise RuntimeError(f"exception during server config: {e}")

    
    def __init__(self) -> None:
        try:
            self._clients : set[Client] = set()
            Backend.refresh_status()
            try:
                # minecraft socket
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.bind((Server._server_ip, Server._server_port))
                self._server_socket.listen(Server._server_max_clients)
                print(f"DEBUG: server_sock: {self._server_socket.getsockname()}")
            except Exception as e:
                raise RuntimeError(f"Minecraft socket: {e}")
            try:
                # control socket
                self._ctrl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._ctrl_socket.bind((Server._server_ip, Server._ctrl_port))
                self._ctrl_socket.listen(1)
            except Exception as e:
                raise RuntimeError(f"Control socket: {e}")
        except Exception as e:
            raise RuntimeError(f"Exception during server init: {e}")
        
    def start(self) -> None:
        try:
            shutdown = False

            while not shutdown:
                sockets = [self._server_socket, self._ctrl_socket]
                readyl, _, _ = select.select(sockets, [], [])

                if self._ctrl_socket in readyl:
                    control_sock, _ = self._ctrl_socket.accept()
                    try:
                        data = control_sock.recv(4)
                        if data == b'STOP':
                            shutdown = True
                        else:
                            raise ValueError("unexpected message received on the control socket")
                    except Exception as e:
                        raise RuntimeError(f"shutdown: {e}")
                    finally:
                        try:
                            control_sock.close()
                        except Exception as e:
                            raise RuntimeError(f"closing ctrl client:  {e}")
                elif self._server_socket in readyl and not shutdown:
                    client_sock, addr = self._server_socket.accept()

                    if addr[0] not in Server._allowed_ips:
                        continue

                    client = Client(client_sock, addr)
                    self._clients.add(client)
                    try:
                        print(f"LOG: {client}")
                        print(f"LOG: client set size: {len(self._clients)}")
                        
                        self._handle_client(client)

                        print(f"LOG: client set size: {len(self._clients)}")

                    except Exception as e:
                        raise RuntimeError(f"client handling: {e}")
                    
        except Exception as e:
            raise RuntimeError(f"server.start(): {e}")
        finally:
            try:
                self._ctrl_socket.close()
            except Exception as e:
                 raise RuntimeError(f"server.start() closing ctrl_socket:  {e}")
            try:
                self._server_socket.close()
            except Exception as e:
                raise RuntimeError(f"server.start() closing mc_socket:  {e}")
            print("Server stopped")


    def _handle_client(self, client: Client) -> None:
            try:
                if Backend.get_status():
                    print("LOG: backend online, forwarding")

                    self._forward(client)
                    return
                
            except Exception as e:
                raise RuntimeError(f"forwarding: {e}")

            try:
                handshake = Packet(client)
                handshake.read()
                print(handshake.data)

                if len(handshake.data) < 2:
                    raise ValueError("wrong format")

                if handshake.data[1] != Null.inbound.handshake:
                    raise ValueError("must be a handshake")
                
            except Exception as e:
                raise RuntimeError(f"first packet: {e}")
            
            try:
                # If the first packet was a status handshake, then the client will immedietly send a status request
                if handshake.data[1] is Null.inbound.handshake and handshake.data[5] == state.Status:
                    status_req = Packet(client)
                    status_req.read()
                    print(status_req.data)
                        
                    if status_req.data[1] is Status.inbound.status_request:
                        status_req.send(Status.outbound.status_response)
                        # Then the client sends a ping request
                        ping_req = Packet(client)
                        ping_req.read()
                        print(ping_req.data)

                        if ping_req.data[1] is Status.inbound.ping_request:
                            ping_req.send(Status.outbound.pong_response)

                            # Exchange done, removing client
                            try:
                                self._clients.remove(client)
                            except KeyError:
                                print(f"ERROR: no client key found")
                            try:
                                client.connection.close()
                            except Exception as e:
                                raise RuntimeError(f"closing client after pong_response: {e}")

            except Exception as e:
                raise RuntimeError(f"status handshake: {e}")
            
            try:
                # If the first packet was a login handshake, then the client will immedietly send a start_login
                if handshake.data[1] is Null.inbound.handshake and handshake.data[5] == state.Login:
                    login_start = Packet(client)
                    login_start.read()
                    print(login_start.data)

                    if login_start.data[1] is Login.inbound.login_start:
                        client.updateState(state.Forwarding)

                        login_start.send(Login.outbound.disconnect_login)

                        if  Backend.start():
                            print("LOG: backend start success")
                            Backend.refresh_status()

                        try:
                            self._clients.remove(client)
                        except KeyError:
                            print(f"ERROR: no client key found")
                        try:
                            client.connection.close()
                        except Exception as e:
                            raise RuntimeError(f"closing client after login_start: {e}")

            except Exception as e:
                raise RuntimeError(f"login handshake: {e}")

    def _forward(self, client: Client) -> None:
        client.updateState(state.Forwarding)
        backend = Backend(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        
        try:
            backend.connection.connect((Backend.ip, Backend.port))
        except Exception as e:
            backend.connection.close()
            raise RuntimeError(f"backend connection failed: {e}")
        
        try:
            client.connection.setblocking(True)
            backend.connection.setblocking(True)
            while True:
                rlist, _, _ = select.select([client.connection, backend.connection], [], [])
                for sock in rlist:
                    if sock is client.connection:
                        data = None
                        try:
                            data = client.connection.recv(65536)
                        except BlockingIOError:
                            data = None
                        if not data:
                            # klient zamknął
                            break
                        backend.connection.sendall(data)
                    else:
                        data = None
                        try:
                            data = backend.connection.recv(65536)
                        except BlockingIOError:
                            data = None
                        if not data:
                            # klient zamknął
                            break
                        client.connection.sendall(data)
        except Exception as e:
            raise RuntimeError(f"forwarding loop: {e}")
        finally:
            try: 
                backend.connection.close()
            except Exception as e:
                raise RuntimeError(f"closing backend connection: {e}")
            try: 
                client.connection.close()
            except Exception as e:
                raise RuntimeError(f"closing client connection: {e}")
            try:
                self._clients.remove(client)
            except Exception as e:
                raise RuntimeError(f"removing client: {e}")


if __name__ == '__main__':
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--stop":
            config = dotenv_values(".env")
            ctrl_port = int(config["CTRL_PORT"] or "25566") 
            
            with socket.create_connection(("127.0.0.1", ctrl_port), timeout=2) as s:
                s.sendall(b"STOP")
            
            print("Stop signal sent.")
            sys.exit(0)
    except Exception as e:
        print(f"ERROR: server shutdown command: {e}")

    try:
        srv = Server()
        srv.start()
    except Exception as e:
        print(f"ERROR: {e}")