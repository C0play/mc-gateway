import bisect
import socket
from operator import itemgetter

from .protocol import BaseProtocol, HandshakePacket
from .version766 import Protocol as Protocol766


class ProtocolFactory:

    versions = [
        (766, Protocol766),
    ]


    @classmethod
    def get(cls, client_socket: socket.socket) -> BaseProtocol:
        """
        Implicitly reads a handhshake packet and fetches the correct protocol version.

        Args:
            client_socket: The socket to read packets from.

        Returns:
            BaseProtocol: Protocol class version requested by the client.
        """

        handshake = HandshakePacket(client_socket)
        handshake.read()

        idx = bisect.bisect_left(
            cls.versions,
            handshake.data.version,
            key = itemgetter(0),
        )

        if cls.versions[idx][0] == handshake.data.version:
            return cls.versions[idx][1](client_socket, handshake)

        return cls.versions[idx - 1][1](client_socket, handshake)
