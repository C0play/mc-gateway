from enum import IntEnum
from ..mc_types.mc_types import encodeVint
from ..mc_types.mc_types import encodeString

class packetIDs(IntEnum):
    disconnect_login = 0x00

def writeDisconnect(msg : str) -> bytes:

    packet_id = encodeVint(packetIDs.disconnect_login)
    packet_data = encodeString(msg)
    packet_len = encodeVint((len(packet_id) + len(packet_data)))

    return packet_len + packet_id + packet_data
