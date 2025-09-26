import socket
from typing import overload, Literal
from ..mc_types import mc_types as mct
from enum import IntEnum
from dataclasses import dataclass

class intent(IntEnum):
    Null = 0
    Status = 1
    Login = 2
    Transfer = 3

@dataclass
class Null(IntEnum):
    class inbound(IntEnum):
        handshake = 0x00

@dataclass
class Status():
    class inbound(IntEnum):
        status_request = 0x00
        ping_request = 0x01
    class outbound(IntEnum):
        status_response = 0x00
        pong_response = 0x01

@dataclass
class Login():

    class inbound(IntEnum):
        login_start = 0x00

    class outbound(IntEnum):
        disconnect_login = 0x00

class Packet:
    state = intent.Null

    @classmethod
    def updateState(cls, newState : int):
        cls.state = newState

    @overload
    def __init__(self, mode : Literal['r'], client : socket.socket) -> None: ...

    @overload
    def __init__(self, mode : Literal['w'], client : socket.socket, data : bytes) -> None: ...

    def __init__(self, mode : Literal['r', 'w'], client : socket.socket, data : bytes | None = None):
        self.data = []
        if mode == 'r':
            packet_length = mct.read_VarInt(client)
            packet_proto = mct.read_VarInt(client)

            match Packet.state:
                case intent.Null:
                    if packet_proto != Null.inbound.handshake:
                        raise RuntimeError(f"At null packet state, a packet with an undefined protocol has been received: {hex(packet_proto)}")
                        
                    proto_version = mct.read_VarInt(client)
                    addr = mct.read_String(client)
                    port =  mct.read_u_short(client)
                    new_intent =  mct.read_VarInt(client)

                    Packet.updateState(new_intent)
                    if Packet.state != new_intent:
                        raise RuntimeError("Packet state has not been updated correctly")
                                
                    self.data = [packet_length, Null.inbound.handshake, proto_version, addr, port, new_intent]

                case intent.Status:
                    if packet_proto == Status.inbound.status_request:
                        if packet_length == 1:
                            self.data = [packet_length, Status.inbound.status_request]
                        else: # It's a handshake with login intent
                            proto_version = mct.read_VarInt(client)
                            addr = mct.read_String(client)
                            port =  mct.read_u_short(client)
                            new_intent =  mct.read_VarInt(client)

                            Packet.updateState(new_intent)
                            if Packet.state != new_intent:
                                raise RuntimeError("Packet state has not been updated correctly")
                                        
                            self.data = [packet_length, Null.inbound.handshake, proto_version, addr, port, new_intent]

                    if packet_proto == Status.inbound.ping_request:
                        payload = mct.read_long(client)
                        self.data = [packet_length, Status.inbound.ping_request, payload]

                case intent.Login:
                    if packet_proto == Login.inbound.login_start:
                        name = mct.read_String(client)
                        uuid = mct.read_uuid(client)
                        self.data = [packet_length, Login.inbound.login_start, name, uuid]
                case intent.Transfer:
                    pass
                case _:
                    # Debug
                    print("DEBUG: base case triggered")
                    # -----
                    self.data = [packet_length, hex(packet_proto)]
        
        elif mode == 'w':
            if data != None:
                client.sendall(data)

    @classmethod
    def write_status_response(cls):
        msg = """{
                "version": {
                    "name": "1.21.8",
                    "protocol": 772
                },
                "players": {
                    "max": 20,
                    "online": 1
                },
                "description": {
                    "text": "Hello, world!"
                },
                "enforcesSecureChat": false
            }"""
        
        packet_id = mct.write_VarInt(Status.outbound.status_response)
        packet_data = mct.write_String(msg)

        packet_body = packet_id + packet_data
        packet_len = mct.write_VarInt(len(packet_body))
        return packet_len + packet_body
    
    def write_pong_response(self):
        packet_id = mct.write_VarInt(Status.outbound.pong_response)
        packet_data = self.data[2]

        packet_body = packet_id + packet_data
        packet_len = mct.write_VarInt(len(packet_body))
        return packet_len + packet_body
    
    @classmethod
    def writeDisconnect(cls, msg : str):

        packet_id = mct.write_VarInt(Login.outbound.disconnect_login)
        packet_data = mct.write_String(msg)

        packet_body = packet_id + packet_data
        packet_len = mct.write_VarInt(len(packet_body))
        return packet_len + packet_body
