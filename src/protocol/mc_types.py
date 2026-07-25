import socket
from uuid import UUID

from src.exceptions import BadRequestError

SEGMENT_BITS=127
CONTINUE_BIT=128

# ----- Decoding -----

def read_uuid(sock: socket.socket) -> UUID:
    """Reads a UUID from the socket."""
    try:
        buffer = sock.recv(16)
        return UUID(bytes=buffer)
    except OSError as e:
        raise ConnectionError(f"uuid: connection closed: {e}")


def read_u_short(sock: socket.socket) -> int:
    """Reads an unsigned short (2 bytes) from the socket."""
    try:
        buffer = sock.recv(2)
        return int.from_bytes(buffer, byteorder='big', signed=False)
    except OSError as e:
        raise ConnectionError(f"short: connection closed: {e}")


def read_long(sock: socket.socket) -> int:
    """Reads a signed long (8 bytes) from the socket."""
    try:
        buffer = sock.recv(8)
        return int.from_bytes(buffer, byteorder='big', signed=True)
    except OSError as e:
        raise ConnectionError(f"long: connection closed: {e}")


def read_varint(sock: socket.socket) -> int:
    """Reads a VarInt from the socket."""
    try:
        i = 0
        res = 0
        buffer = sock.recv(1)
        if not buffer:
            raise BadRequestError("varint: no initial data received")

        while (buffer[0] & CONTINUE_BIT):
            res += (buffer[0] ^ CONTINUE_BIT) << (i * 7)

            buffer = sock.recv(1)
            if not buffer:
                raise BadRequestError("varint: no data received after continueation bit")

            i += 1
            if i > 5:  # VarInt max is 5 bytes
                raise BadRequestError("varint: too long")

        res += buffer[0] << (i * 7)
        return res

    except OSError as e:
        raise ConnectionError(f"varint: connection closed: {e}")


def read_String(sock: socket.socket) -> str:
    """Reads a VarInt-prefixed UTF-8 string from the socket."""
    try:
        length = read_varint(sock)
        if length < 0 or length > 32767:
            raise BadRequestError(f"string: invalid length: {length}")

        buffer = sock.recv(length)
        if len(buffer) != length:
            raise BadRequestError(f"string: expected {length} bytes, got {len(buffer)}")

        msg =  buffer.decode(encoding="utf8")
        return msg
    except UnicodeDecodeError as e:
        raise BadRequestError(f"string: invalid UTF-8 data: {e}")
    except OSError as e:
        raise ConnectionError(f"string: connection closed while reading: {e}")


# ----- Encoding -----

def write_string(msg: str) -> bytearray:
    """Encodes a string into a VarInt-prefixed bytearray."""
    data = bytearray(msg, encoding="utf8")
    msg_len = write_varInt(len(data))
    return msg_len + data


def write_varInt(value: int) -> bytearray:
    """Encodes an integer into a VarInt bytearray."""
    val = value
    bytes = bytearray()
    while True:
        byte = val & SEGMENT_BITS

        val >>= 7

        if val > 0:
            byte |= CONTINUE_BIT
            bytes.append(byte)
        else:
            bytes.append(byte)
            break

    return bytes


def write_long(value: int) -> bytearray:
    """Encodes a signed long into 8 big-endian bytes."""
    return bytearray(value.to_bytes(8, byteorder='big', signed=True))


def write_uuid(uuid: UUID) -> bytearray:
    """Encodes a UUID into bytes."""
    return bytearray(uuid.bytes)


def write_u_short(value : int) -> bytearray:
    """Encodes an unsigned short into 2 big-endian bytes."""
    return bytearray(value.to_bytes(2, byteorder='big', signed=False))
