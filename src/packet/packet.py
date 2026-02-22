from enum import IntEnum

from ..gateway.client import State
from ..gateway.client import Client
from . import mc_types as mct


class Null():
    class serverbound(IntEnum):
        handshake = 0x00


class Status():
    class serverbound(IntEnum):
        status_request = 0x00
        ping_request = 0x01
    class clientbound(IntEnum):
        status_response = 0x00
        pong_response = 0x01


class Login():
    class serverbound(IntEnum):
        login_start = 0x00
    class clientbound(IntEnum):
        disconnect_login = 0x00



class Packet:
    """
    Represents a Minecraft protocol packet.
    Handles reading packet data from a client socket and parsing it based on the client's state.
    """

    def __init__(self, client: Client):
        self.client = client
        self.data = []


    def read(self) -> 'Packet':
        """Parse a minecraft packet received from the client."""
        try:
            packet_length = mct.read_VarInt(self.client.socket)
            packet_proto = mct.read_VarInt(self.client.socket)

            match self.client.state:
                case State.Null:
                    if packet_length == 0xFE: # Legacy ping uses a different format
                        raise NotImplementedError("legacy packet")
                    
                    if packet_proto != Null.serverbound.handshake:
                        raise ValueError(f"at null packet state, a packet with an undefined protocol has been received: {packet_proto}")
                        
                    proto_version = mct.read_VarInt(self.client.socket)
                    if proto_version != 772:
                        raise NotImplementedError(f"unsupported protocol version: {proto_version}")
                    
                    addr = mct.read_String(self.client.socket)
                    port =  mct.read_u_short(self.client.socket)
                    new_intent =  mct.read_VarInt(self.client.socket)

                    self.client.updateState(new_intent)
                    self.data = [packet_length, Null.serverbound.handshake, proto_version, addr, port, new_intent]

                case State.Status:
                    if packet_proto == Status.serverbound.status_request:
                        self.data = [packet_length, Status.serverbound.status_request]
                    elif packet_proto == Status.serverbound.ping_request:
                        payload = mct.read_long(self.client.socket)
                        self.data = [packet_length, Status.serverbound.ping_request, payload]
                    else: 
                        self.data = [packet_length, hex(packet_proto)]
                        raise ValueError(f"at status packet state, a packet with an undefined protocol has been received: {hex(packet_proto)}") 
                case State.Login:
                    if packet_proto == Login.serverbound.login_start:
                        name = mct.read_String(self.client.socket)
                        uuid = mct.read_uuid(self.client.socket)
                        self.data = [packet_length, Login.serverbound.login_start, name, uuid]
                    else: 
                        self.data = [packet_length, hex(packet_proto)]
                        raise ValueError(f"at login packet state, a packet with an undefined protocol has been received: {hex(packet_proto)}") 

                case State.Transfer:
                    self.data = [packet_length, hex(packet_proto)]
                    raise NotImplementedError(f"transfer packet state: {hex(packet_proto)}") 

                case default:
                    self.data = [packet_length, hex(packet_proto)]
                    raise ValueError(f"unexpected state in Packet class: {default}")
            
            return self
                
        except NotImplementedError as e:
            self.data = []
            raise e 
        except Exception as e:
            self.data = []
            raise RuntimeError(f"failed to read packet: {e}")


    def respond(self, login_disc_msg: str | None = None, colour: str | None = None) -> None:
        """Send a response to the client. If the incoming packet was a login_start, then a disconnect_login
        will be sent with the provided message and colour (or default)."""
        data = None
        packet_type = self.data[1]
        if packet_type is Status.serverbound.status_request:
            try:
                data = Packet._encode_status_response()
            except Exception as e:
                raise RuntimeError(f"send status_res: {e}")
        elif packet_type is Status.serverbound.ping_request:
            try:
                data = self._encode_pong_response()
            except Exception as e:
                raise RuntimeError(f"send pong_res: {e}")
        elif packet_type is Login.serverbound.login_start:
            try:
                data = Packet._encode_disconnect_login(login_disc_msg, colour)
            except Exception as e:
                raise RuntimeError(f"send disconnect: {e}")
        else:
            raise ValueError("invalid packet type")
        
        self.client.socket.sendall(data)
    

    def reencode(self) -> bytearray:
        """Reencode the received packet data"""
        data = None
        packet_type = self.data[1]
        if packet_type is Null.serverbound.handshake:
            try:
                data = self._encode_login_handshake()
            except Exception as e:
                raise RuntimeError(f"send login_start: {e}")
        elif packet_type is Login.serverbound.login_start:
            try:
                data = self._encode_login_start()
            except Exception as e:
                raise RuntimeError(f"send login_start: {e}")
        else:
            raise ValueError("this packet type can not be forwarded")
        
        return data


    @staticmethod
    def _encode_disconnect_login(disconnect_msg: str | None, colour: str | None) -> bytearray:
        msg = '{text: "Server is starting, please wait.", color: "green"}'
        if disconnect_msg:
            msg_colour = colour if colour else "green"
            msg = f"""{{text: "{disconnect_msg}", color: "{msg_colour}"}}"""
            
        packet_id = mct.write_varInt(Login.clientbound.disconnect_login)
        packet_data = mct.write_string(msg)
        return Packet._assemble_packet(packet_id, packet_data)
    

    @staticmethod
    def _encode_status_response() -> bytearray:
        txt = "Press Join to check your server's status!"
        msg = f"""{{
                    "version": {{
                        "name": "1.21.8",
                        "protocol": 772
                    }},
                    "players": {{
                        "max": 0,
                        "online": 0
                    }},
                    "description": {{
                        "text": "{txt}"
                    }},
                    "enforcesSecureChat": "false"
                }}"""
        
        packet_id = mct.write_varInt(Status.clientbound.status_response)
        packet_data = mct.write_string(msg)
        return Packet._assemble_packet(packet_id, packet_data)
    

    def _encode_pong_response(self) -> bytearray:
        packet_id = mct.write_varInt(Status.clientbound.pong_response)
        packet_data = mct.write_long(self.data[2])
        return Packet._assemble_packet(packet_id, packet_data)
   
   
    def _encode_login_handshake(self) -> bytearray:
        packet_id = mct.write_varInt(Null.serverbound.handshake)
        proto_ver = mct.write_varInt(self.data[2])
        addr = mct.write_string(self.data[3])
        port = mct.write_u_short(self.data[4])
        intent = mct.write_varInt(self.data[5])
        packet_data = proto_ver + addr + port + intent
        return Packet._assemble_packet(packet_id, packet_data)


    def _encode_login_start(self) -> bytearray:
        packet_id = mct.write_varInt(Login.serverbound.login_start)
        name = mct.write_string(self.data[2])
        uuid = mct.write_uuid(self.data[3])
        return Packet._assemble_packet(packet_id, name + uuid)


    @staticmethod
    def _assemble_packet(packet_id: bytearray, packet_data: bytearray) -> bytearray:
        packet_body = packet_id + packet_data
        packet_len = mct.write_varInt(len(packet_body))
        return  packet_len + packet_body

        
