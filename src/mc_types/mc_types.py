import socket
from uuid import UUID

SEGMENT_BITS=127
CONTINUE_BIT=128

# ----- Decoding -----

def read_uuid(sock: socket.socket) -> UUID:
    buffer = sock.recv(16)
    return UUID(bytes=buffer)

def read_u_short(sock: socket.socket) -> int:
    buffer = sock.recv(2)
    return (buffer[0] << 8) | buffer[1]

def read_long(sock: socket.socket) -> int:
    try:
        buffer = sock.recv(8)
        return int.from_bytes(buffer, byteorder='big', signed=True)
    except Exception as e:
        raise RuntimeError(f"Exception in read_long: {e}")

def read_VarInt(sock: socket.socket) -> int:
    res = 0
    
    buffer = sock.recv(1)
    i = 0
    while (buffer[0] & CONTINUE_BIT):
        res += (buffer[0] ^ CONTINUE_BIT) << (i * 7)
        
        buffer = sock.recv(1)
        i += 1
    
    res += buffer[0] << (i * 7)

    return res
    
def read_String(sock: socket.socket) -> str:
    length = read_VarInt(sock)
    orig_msg = sock.recv(length)
    msg = orig_msg
    try:
        msg = msg.decode(encoding="utf8")
        return msg
    except Exception as e:
        print(f"Exception in read_String: {e} {orig_msg}")
        return ""
    
# ----- Encoding -----

def write_String(msg: str) -> bytearray:
    data = bytearray(msg, encoding="utf8")
    msg_len = write_VarInt(len(data))
    return msg_len + data


def write_VarInt(value: int) -> bytearray:
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
    try:
        return bytearray(value.to_bytes(8, byteorder='big', signed=True))
    except Exception as e:
        raise RuntimeError(f"Exception in write_long: {e}")
    
def write_uuid(uuid: UUID) -> bytearray:
    return bytearray(uuid.bytes)