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
    return int.from_bytes(buffer, byteorder='big', signed=False)

def read_long(sock: socket.socket) -> int:
    try:
        buffer = sock.recv(8)
        return int.from_bytes(buffer, byteorder='big', signed=True)
    except Exception as e:
        raise RuntimeError(f"Exception in read_long: {e}")

def read_VarInt(sock: socket.socket) -> int:
    try:
        i = 0
        res = 0
        buffer = sock.recv(1)
        if not buffer:
            raise BufferError()
        
        while (buffer[0] & CONTINUE_BIT):
            res += (buffer[0] ^ CONTINUE_BIT) << (i * 7)
            
            buffer = sock.recv(1)
            if not buffer:
                raise BufferError()
            
            i += 1
            if i > 5:  # VarInt max is 5 bytes
                raise ValueError("VarInt too long")
        
        res += buffer[0] << (i * 7)
        return res

    except IndexError:
        raise IndexError(f"IndexError while reading VarInt")
    except BufferError:
        raise BufferError(f"no data received after continuation bit")
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        raise RuntimeError(f"connection closed while reading VarInt: {e}")
    except Exception as e:
        raise RuntimeError(f"read_VarInt failed: {e}")

def read_String(sock: socket.socket) -> str:
    try:
        length = read_VarInt(sock)
        if length < 0 or length > 32767:
            raise ValueError(f"Invalid string length: {length}")
        
        buffer = sock.recv(length)
        if len(buffer) != length:
            raise ValueError(f"Expected {length} bytes, got {len(buffer)}")
        
        msg =  buffer.decode(encoding="utf8")
        return msg
    except UnicodeDecodeError as e:
        raise RuntimeError(f"invalid UTF-8 data: {e}")
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        raise RuntimeError(f"connection closed while reading string: {e}")
    except Exception as e:
        raise RuntimeError(f"read_String failed: {e}")

    
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

def write_u_short(value : int) -> bytearray:
    return bytearray(value.to_bytes(2, byteorder='big', signed=False))