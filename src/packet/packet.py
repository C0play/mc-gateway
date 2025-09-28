from typing import Literal
from enum import IntEnum

from ..watcher.client import state
from ..watcher.client import Client
from ..watcher.backend import Backend 
from ..mc_types import mc_types as mct

class Null(IntEnum):
    class inbound(IntEnum):
        handshake = 0x00

class Status():
    class inbound(IntEnum):
        status_request = 0x00
        ping_request = 0x01
    class outbound(IntEnum):
        status_response = 0x00
        pong_response = 0x01

class Login():
    class inbound(IntEnum):
        login_start = 0x00
    class outbound(IntEnum):
        disconnect_login = 0x00

class Packet:
    def __init__(self, client: Client):
        self.client = client
        self.data = []

    def read(self) -> None:
        packet_length = mct.read_VarInt(self.client.connection)
        packet_proto = mct.read_VarInt(self.client.connection)

        match self.client.state:
            case state.Null:
                if packet_proto != Null.inbound.handshake:
                    raise ValueError(f"at null packet state, a packet with an undefined protocol has been received: {hex(packet_proto)}")
                    
                proto_version = mct.read_VarInt(self.client.connection)
                addr = mct.read_String(self.client.connection)
                port =  mct.read_u_short(self.client.connection)
                new_intent =  mct.read_VarInt(self.client.connection)

                self.client.updateState(new_intent)
                self.data = [packet_length, Null.inbound.handshake, proto_version, addr, port, new_intent]

            case state.Status:
                if packet_proto == Status.inbound.status_request:
                    self.data = [packet_length, Status.inbound.status_request]
                elif packet_proto == Status.inbound.ping_request:
                    payload = mct.read_long(self.client.connection)
                    self.data = [packet_length, Status.inbound.ping_request, payload]
                else: 
                    self.data = [packet_length, hex(packet_proto)]
                    raise ValueError(f"at status packet state, a packet with an undefined protocol has been received: {hex(packet_proto)}") 
            case state.Login:
                if packet_proto == Login.inbound.login_start:
                    name = mct.read_String(self.client.connection)
                    uuid = mct.read_uuid(self.client.connection)
                    self.data = [packet_length, Login.inbound.login_start, name, uuid]
                else: 
                    self.data = [packet_length, hex(packet_proto)]
                    raise ValueError(f"at login packet state, a packet with an undefined protocol has been received: {hex(packet_proto)}") 

            case state.Transfer:
                self.data = [packet_length, hex(packet_proto)]
                raise ValueError(f"transfer packet state has been reached (unimplemented): {hex(packet_proto)}") 

            case default:
                self.data = [packet_length, hex(packet_proto)]
                raise ValueError(f"unexpected state in Packet class: {default}")
    
    def send(self, 
             packet_type : Literal[Status.outbound.status_response,
                                   Status.outbound.pong_response,
                                   Login.inbound.login_start,
                                   Login.outbound.disconnect_login],) -> None:
        data = None
        if packet_type is Status.outbound.status_response:
            try:
                data = Packet._encode_status_response()
            except Exception as e:
                raise RuntimeError(f"send status_res: {e}")
        elif packet_type is Status.outbound.pong_response:
            try:
                data = self._encode_pong_response()
            except Exception as e:
                raise RuntimeError(f"send pong_res: {e}")
        elif packet_type is Login.inbound.login_start:
            try:
                data = self._encode_login_start()
            except Exception as e:
                raise RuntimeError(f"send login_start: {e}")
        elif packet_type is Login.outbound.disconnect_login:
            try:
                data = Packet._encode_disconnect_login()
            except Exception as e:
                raise RuntimeError(f"send disconnect: {e}")
        else:
            raise ValueError("invalid packet type")
        
        self.client.connection.sendall(data)

    @staticmethod
    def _assemble_packet(packet_id: bytearray, packet_data: bytearray) -> bytearray:
        packet_body = packet_id + packet_data
        packet_len = mct.write_VarInt(len(packet_body))
        return  packet_len + packet_body

    @staticmethod
    def _encode_disconnect_login() -> bytearray:
        msg = '{text: "Server is starting, please wait.", color: "green"}'
        packet_id = mct.write_VarInt(Login.outbound.disconnect_login)
        packet_data = mct.write_String(msg)
        return Packet._assemble_packet(packet_id, packet_data)
    
    @staticmethod
    def _encode_status_response() -> bytearray:
        b = """{
                        "version": {
                            "name": "1.21.8",
                            "protocol": 772
                        },
                        "players": {
                            "max": 20,
                            "online": 0
                        },
                        "description": {
                            "text": """
        e = """
                        },
                        "enforcesSecureChat": false
                    }"""
        
        if Backend._status:
            txt = "\"Server online!\""
        else:
            txt = "\"Server offline, press Join to start it!\""
        
        msg = b + txt + e
        packet_id = mct.write_VarInt(Status.outbound.status_response)
        packet_data = mct.write_String(msg)
        return Packet._assemble_packet(packet_id, packet_data)
    
    def _encode_login_start(self) -> bytearray:
        packet_id = mct.write_VarInt(Login.inbound.login_start)
        name = mct.write_String(self.data[2])
        uuid = mct.write_uuid(self.data[3])
        return Packet._assemble_packet(packet_id, name + uuid)
    
    def _encode_pong_response(self) -> bytearray:
        packet_id = mct.write_VarInt(Status.outbound.pong_response)
        packet_data = mct.write_long(self.data[2])
        return Packet._assemble_packet(packet_id, packet_data)
    
        
