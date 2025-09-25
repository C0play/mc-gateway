SEGMENT_BITS=127
CONTINUE_BIT=128


def encodeVint(value : int) -> bytearray:
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

def decodeVint(bytes : bytes) -> tuple[int, int] :
    i = 0
    res = 0
    while bytes[i] & CONTINUE_BIT:
        num = bytes[i] ^ CONTINUE_BIT
        num <<= (i * 7)
        res += num
        i += 1

    num = bytes[i]
    num <<= (i * 7)
    res += num
    
    return (res, i + 1)

def encodeString(msg : str) -> bytearray:
    data = bytearray(msg, encoding="utf8")
    msg_len = encodeVint(len(data))
    return msg_len + data

def decodeString(msg : bytes) -> tuple[str, int]:
    msg_length, count = decodeVint(msg)
    return (msg[count:].decode(encoding="utf8"), count)