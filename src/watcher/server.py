import csv
import sys
import socket
import select
import threading
from uuid import UUID
from dotenv import dotenv_values

from ..packet.packet import Packet
from ..packet.packet import Null
from ..packet.packet import Status 
from ..packet.packet import Login

from .client import Client
from .client import state

from .backend import Backend

class Server:

    _allowed_players: set[tuple[str, UUID]] = set()
    with open("allow_list.csv") as allow_list:
        reader = csv.reader(allow_list)
        for row in reader:
            name = row[0]
            uuid = UUID(row[1])
            _allowed_players.add((name, uuid))
    
    try:
        _config = dotenv_values(".env")
            
        _server_ip = _config["SERVER_IP"]
        _server_port = int(_config["SERVER_PORT"] or 25567)
        _server_domain = _config["DOMAIN"]
        _server_max_clients = int(_config["CLIENTS"] or "4" )

        _ctrl_port = int(_config["CTRL_PORT"] or 25566)

        # single backend for now
        _backend = Backend(25565, "Minecraft", "minecraft-mc-1")

    except Exception as e:
        raise RuntimeError(f"exception during server config: {e}")

    
    def __init__(self) -> None:
        try:
            self._clients : set[Client] = set()
            self._clients_lock = threading.Lock()
            self._shutdown = False
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
            while not self._shutdown:
                sockets = [self._server_socket, self._ctrl_socket]
                readyl, _, _ = select.select(sockets, [], [])

                if self._ctrl_socket in readyl:
                    control_sock, _ = self._ctrl_socket.accept()
                    try:
                        self._cli_parse(control_sock)
                    except Exception as e:
                        print(f"ERROR: control socket: {e}")
                    
                elif self._server_socket in readyl and not self._shutdown:
                    client_sock, addr = self._server_socket.accept()
                    client = Client(client_sock, addr)
                    try:
                        print(f"LOG: new: {client}")
                        print(f"LOG: total clients: {len(self._clients)}")

                        t = threading.Thread(target=self._handle_client, daemon=True, args=(client,))
                        t.start()

                    except Exception as e:
                        print(f"ERROR: client handling: {e}")

        except Exception as e:
            raise RuntimeError(f"server.start: {e}")
        finally:
            try:
                self._ctrl_socket.close()
            except Exception as e:
                 raise RuntimeError(f"server.start closing ctrl_socket:  {e}")
            try:
                self._server_socket.close()
            except Exception as e:
                raise RuntimeError(f"server.start closing mc_socket:  {e}")
            print("Server stopped")


    def _handle_client(self, client: Client) -> None:
        try:
            try:
                with self._clients_lock:
                    self._clients.add(client)
                        
                handshake = Packet(client)
                handshake.read()
                print(handshake.data)

                if handshake.data[3] != Server._server_domain:
                    return

                if len(handshake.data) < 2:
                    raise ValueError("wrong format")

                if not handshake.data[1] is Null.serverbound.handshake:
                    raise ValueError("must be a handshake")
                
            except Exception as e:
                raise RuntimeError(f"first packet: {e}")
            
            try:
                # If the first packet was a status handshake, then the client will immedietly send a status request
                if handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == state.Status:
                    status_req = Packet(client)
                    status_req.read()
                    print(status_req.data)
                        
                    if status_req.data[1] is Status.serverbound.status_request:
                        status_req.respond()
                        # Then the client sends a ping request
                        ping_req = Packet(client)
                        ping_req.read()
                        print(ping_req.data)

                        if ping_req.data[1] is Status.serverbound.ping_request:
                            ping_req.respond()

                    return
            except Exception as e:
                raise RuntimeError(f"status handshake: {e}")
            
            try:
                # If the first packet was a login handshake, then the client will immedietly send a start_login
                if handshake.data[1] is Null.serverbound.handshake and handshake.data[5] == state.Login:
                    login_start = Packet(client)
                    login_start.read()
                    print(login_start.data)

                    if not (login_start.data[2], login_start.data[3]) in Server._allowed_players:
                        print(f"LOG: unknown player: {(login_start.data[2], login_start.data[3])}")
                        return

                    if login_start.data[1] is Login.serverbound.login_start:
                        if Server._backend.get_ctnr_status():
                            try:
                                Server._backend.open_connection()
                            except Exception as e:
                                raise RuntimeError(f"exception while connecting to backend {e}")
                            try:
                                print("LOG: backend online, forwarding")
                                handshake.forward(Server._backend)
                                login_start.forward(Server._backend)

                                self._forward(client, Server._backend)
                                
                                return
                            
                            except Exception as e:
                                raise RuntimeError(f"forwarding: {e}")
                        
                        else:
                            login_start.respond()

                            if  Server._backend.container_start():
                                print("LOG: backend start successfull")
                            else:
                                print("LOG: backend start failed")

            except Exception as e:
                raise RuntimeError(f"login handshake: {e}")
        finally:
            try:
                client.connection.close()
            except Exception as e:
                raise RuntimeError(f"closing client {e}")
            try: 
                Server._backend.connection.close()
            except Exception as e:
                raise RuntimeError(f"closing backend connection: {e}")
            try:
                with self._clients_lock:
                    self._clients.remove(client)
            except KeyError:
                print(f"ERROR: no client key found")

    def _forward(self, client: Client, backend: Backend) -> None:
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
                            # client closed
                            return
                        backend.connection.sendall(data)
                    else:
                        data = None
                        try:
                            data = backend.connection.recv(65536)
                        except BlockingIOError:
                            data = None
                        if not data:
                            # backend closed
                            return
                        client.connection.sendall(data)
        except Exception as e:
            raise RuntimeError(f"forwarding loop: {e}")
        
    def _cli_parse(self, sock: socket.socket):
        try:
            data = bytearray()
            try:
                while True:
                    buffer = sock.recv(16)
                    if not buffer:
                        break
                    data += buffer
                cmd = data.decode().strip().split()
            except Exception as e:
                raise RuntimeError(f"read error: {e}") 
            match cmd[0]:
                case "--stop":
                    self._shutdown = True
                case "--addp":
                    try:
                        with open("allow_list.csv", mode='a') as allow_list:
                            writer = csv.writer(allow_list)
                            name, uuid_str = cmd[1], cmd[2]
                            uuid = UUID(uuid_str)

                            Server._allowed_players.add((name, uuid))
                            writer.writerow([name, uuid_str])
                    except Exception as e:
                        raise RuntimeError(f"--addp: {e}")
                case default:
                    raise ValueError("unknown command")
        except Exception as e:
            raise RuntimeError(f"cli_parse: {e}")
    
    @classmethod
    def cli_send(cls, cmds: list[str]):
        try:
            if len(cmds) <= 1 or cmds[1] == "":
                raise ValueError("invalid input")
            if cmds[1] == "--addp" and (len(cmds) < 3 or cmds[2] == "" or cmds[3] == ""):
                raise ValueError("invalid addp input")
                
            config = dotenv_values(".env")
            ctrl_port = int(config["CTRL_PORT"] or "25566")

            with socket.create_connection(("127.0.0.1", ctrl_port), timeout=0.1) as s:
                data = ' '.join(cmds[1:])
                s.sendall(data.encode())
        except TimeoutError:
            print(f"ERROR: server cli_send: is not running")
        except Exception as e:
            print(f"ERROR: server cli_send: {e}")

if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            Server.cli_send(sys.argv)
        else:
            srv = Server()
            srv.start()
    except Exception as e:
        print(f"ERROR: {e}")