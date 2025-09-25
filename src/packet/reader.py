from ..mc_types.mc_types import decodeVint
from ..mc_types.mc_types import decodeString


def readDisconnect(packet : bytes):

    packet_len, byte_count1 = decodeVint(packet)
    packet_id, byte_count2 = decodeVint(packet[byte_count1:])
    packet_data, byte_count3 = decodeString(packet[byte_count1 + byte_count2:])

    return f"{packet_len} | {hex(packet_id)} | {packet_data}"
