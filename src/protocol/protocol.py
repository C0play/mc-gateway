import socket
from abc import ABC, abstractmethod

from typing_extensions import Any


from src.exceptions import BadRequestError
from .mc_types import *
from .types import BaseData, HandshakeData, NullPhase


class BasePacket:

    def __init__(self, client_socket: socket.socket) -> None:
        """
        Initializes a packet class.
        Exposes a public `data` property that will hold any data
        read from the client.
        Args:
            client_socket: Socket to read packets from.
        """
        self.client = client_socket
        self.data: Any


    def _read_header(self) -> BaseData:
        """
        Reads the packet length and id.

        Raises:
            BadRequestError: If read data has an incorrect format.
            ConnectionError: If reading from the socket fails.
        """
        try:
            return BaseData(
                length  = read_varint(self.client),
                id      = read_varint(self.client)
            )
        except BadRequestError as e:
            raise BadRequestError(f"packet header: {e}")
        except ConnectionError as e:
            raise ConnectionError(f"packet header: {e}")


    @staticmethod
    def _assemble_packet(id: bytearray, data: bytearray) -> bytearray:
        """Prepends the packet's length to it's payload."""
        body = id + data
        length = write_varInt(len(body))
        return  length + body



class HandshakePacket(BasePacket):

    def read(self) -> None:
        """
        Reads a Handshake packet.

        Raises:
            BadRequestError: If read data has an incorrect format.
            ConnectionError: If reading from the socket fails.
        """
        header = self._read_header()

        if header.id != NullPhase.serverbound.handshake:
            raise BadRequestError(f"received packet with invalid id '{header.id}'")

        try:
            self.data = HandshakeData(
                length  = header.length,
                id      = header.id,
                version = read_varint(self.client),
                address = read_String(self.client),
                port    = read_u_short(self.client),
                intent  = read_varint(self.client)
            )
        except BadRequestError as e:
            raise BadRequestError(f"handshake packet: {e}")
        except ConnectionError as e:
            raise ConnectionError(f"handshake header: {e}")


    def reencode(self) -> bytearray:
        id      = write_varInt(self.data.id)
        version = write_varInt(self.data.version)
        addr    = write_string(self.data.address)
        port    = write_u_short(self.data.port)
        intent  = write_varInt(self.data.intent)

        packet_data = version + addr + port + intent
        return self._assemble_packet(id, packet_data)


    def _read_header(self) -> BaseData:
        if self.client.recv(1, socket.MSG_PEEK) == b'\xFE':
            raise BadRequestError("legacy ping packets are not supported")
        return super()._read_header()



class BaseStatusPacket(ABC, BasePacket):

    @abstractmethod
    def read(self) -> None:
        """
        Reads a Status Request packet.

        Raises:
            BadRequestError: If read data has an incorrect format.
            ConnectionError: If reading from the socket fails.
        """
        ...

    @abstractmethod
    def respond(self, game_version: str, proto_version: int) -> None:
        """
        Sends a Status Response packet.

        Args:
            game_version: For example 1.21.8
            proto_version: For example 773
        
        Raises:
            ConnectionError: If sending the response fails.
        """
        ...


class BasePingPacket(ABC, BasePacket):

    @abstractmethod
    def read(self) -> None:
        """
        Reads a Ping packet.

        Raises:
            BadRequestError: If read data has an incorrect format.
            ConnectionError: If reading from the socket fails.
        """
        ...

    @abstractmethod
    def respond(self) -> None:
        """
        Sends a Pong packet.
        
        Raises:
            ConnectionError: If sending the response fails.
        """
        ...


class BaseLoginPacket(ABC, BasePacket):

    @abstractmethod
    def read(self) -> None:
        """
        Reads a Login Start packet.

        Raises:
            BadRequestError: If read data has an incorrect format.
            ConnectionError: If reading from the socket fails.
        """
        ...

    @abstractmethod
    def respond(self, msg: str, color: str = "green") -> None:
        """
        Sends a Login Disconnect packet.
        
        Raises:
            ConnectionError: If sending the response fails.
        """
        ...

    @abstractmethod
    def reencode(self) -> bytearray:
        """Encodes the packet back into bytes."""
        ...



class BaseProtocol(ABC):

    def __init__(self, client_socket: socket.socket, handshake: HandshakePacket) -> None:
        self.client_socket = client_socket
        self.handshake = handshake


    @property
    def status(self) -> BaseStatusPacket:
        return self._get_status_packet()

    @property
    def ping(self) -> BasePingPacket:
        return self._get_ping_packet()

    @property
    def login(self) -> BaseLoginPacket:
        return self._get_login_packet()


    @abstractmethod
    def _get_status_packet(self) -> BaseStatusPacket:
        ...

    @abstractmethod
    def _get_ping_packet(self) -> BasePingPacket:
        ...

    @abstractmethod
    def _get_login_packet(self) -> BaseLoginPacket:
        ...
