from dataclasses import dataclass
from enum import IntEnum


class NullPhase:

    class serverbound(IntEnum):
        handshake = 0x00


class StatusPhase:

    class serverbound(IntEnum):
        status_request = 0x00
        ping_request = 0x01

    class clientbound(IntEnum):
        status_response = 0x00
        pong_response = 0x01


class LoginPhase:

    class serverbound(IntEnum):
        login_start = 0x00

    class clientbound(IntEnum):
        disconnect_login = 0x00


@dataclass
class BaseData:
    length: int
    id: int


@dataclass
class HandshakeData(BaseData):
    version: int
    address: str
    port: int
    intent: int


class Intent(IntEnum):
    Null = 0
    Status = 1
    Login = 2
    Transfer = 3
