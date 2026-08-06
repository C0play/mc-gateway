import socket

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

        Raises:
            NotImplementedError: If a suitable protocol handler can't be found for the requested version.
        """

        handshake = HandshakePacket(client_socket)
        handshake.read()

        if not cls.versions:
            raise NotImplementedError(f"there are no handlers registered")

        idx = cls._binsearch(handshake.data.version)

        if cls.versions[idx][0] > handshake.data.version:
            raise NotImplementedError(f"there are no handlers for protocol version {handshake.data.version}")

        return cls.versions[idx][1](client_socket, handshake)


    @classmethod
    def _binsearch(cls, version: int) -> int:

        a, b = 0, len(cls.versions) - 1

        while (a <= b):

            m = (a + b) // 2

            if cls.versions[m][0] == version:
                return m

            if cls.versions[m][0] < version:
                a = m + 1
            elif cls.versions[m][0] > version: 
                b = m - 1

        return b