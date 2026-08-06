import socket
from dataclasses import dataclass
from uuid import UUID

from .mc_types import *

from ..exceptions import BadRequestError
from .protocol import (
    BaseLoginPacket,
    BasePingPacket,
    BaseProtocol,
    BaseStatusPacket,
    HandshakePacket,
)
from .types import (
    BaseData,
    LoginPhase,
    StatusPhase,
)


@dataclass
class StatusData(BaseData):
    pass


@dataclass
class PingData(BaseData):
    payload: int


@dataclass
class LoginData(BaseData):
    name: str
    uuid: UUID



class StatusPacket(BaseStatusPacket):

    def read(self) -> None:
        header = self._read_header()
        self.data = StatusData(
            length   = header.length,
            id       = header.id
        )


    def respond(self, game_version: str, proto_version: int) -> None:
        txt = "Press Join to check your server's status!"
        msg = f"""{{
                    "version": {{
                        "name": "{game_version}",
                        "protocol": {proto_version}
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

        id = write_varInt(StatusPhase.clientbound.status_response)
        data = write_string(msg)
        bytes = self._assemble_packet(id, data)
        try:
            self.client.sendall(bytes)
        except OSError as e:
            raise ConnectionError(f"failed to send status response: {e}")



class PingPacket(BasePingPacket):

    def read(self) -> None:
        header = self._read_header()

        try:
            self.data = PingData(
                length  = header.length,
                id      = header.id,
                payload = read_long(self.client)
            )
        except BadRequestError as e:
            raise BadRequestError(f"ping packet: {e}")
        except ConnectionError as e:
            raise ConnectionError(f"ping header: {e}")


    def respond(self) -> None:
        id      = write_varInt(StatusPhase.clientbound.pong_response)
        data    = write_long(self.data.payload)
        bytes   = self._assemble_packet(id, data)
        try:
            self.client.sendall(bytes)
        except OSError as e:
            raise ConnectionError(f"failed to send ping response: {e}")



class LoginPacket(BaseLoginPacket):

    def read(self) -> None:
        header = self._read_header()

        try:
            self.data = LoginData(
                length  = header.length,
                id      = header.id,
                name    = read_String(self.client),
                uuid    = read_uuid(self.client),
            )
        except BadRequestError as e:
            raise BadRequestError(f"login packet: {e}")
        except ConnectionError as e:
            raise ConnectionError(f"login header: {e}")


    def reencode(self) -> bytearray:
        id      = write_varInt(LoginPhase.serverbound.login_start)
        name    = write_string(self.data.name)
        uuid    = write_uuid(self.data.uuid)
        return self._assemble_packet(id, name + uuid)


    def respond(self, msg: str, color: str = "green") -> None:
        msg_json = f"""{{text: "{msg}", color: "{color}"}}"""

        packet_id = write_varInt(LoginPhase.clientbound.disconnect_login)
        packet_data = write_string(msg_json)
        bytes = self._assemble_packet(packet_id, packet_data)
        try:
            self.client.sendall(bytes)
        except OSError as e:
            raise ConnectionError(f"failed to send login response: {e}")



class Protocol(BaseProtocol):

    def __init__(self, client_socket: socket.socket, handshake: HandshakePacket) -> None:

        self._status:   StatusPacket | None = None
        self._ping:     PingPacket   | None = None
        self._login:    LoginPacket  | None = None

        super().__init__(client_socket, handshake)


    def _get_status_packet(self) -> StatusPacket:
        if self._status is not None:
            return self._status

        self._status = StatusPacket(self.client_socket)
        return self._status


    def _get_ping_packet(self) -> PingPacket:
        if self._ping is not None:
            return self._ping

        self._ping = PingPacket(self.client_socket)
        return self._ping


    def _get_login_packet(self) -> LoginPacket:
        if self._login is not None:
            return self._login

        self._login = LoginPacket(self.client_socket)
        return self._login
