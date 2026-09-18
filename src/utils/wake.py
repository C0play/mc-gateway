import socket

from src.exceptions import ServiceError

from .logger import logger


def send_magic_packet(mac):
    """
    Send a magic packet to the specified mac address.

    Args:
        mac (type): Mac address of the host.
    Raises:
        ServiceError: If sending the magic packet fails.
    """
    sanitized_mac = mac
    spacers = [":", "-", "_", " "]
    try:
        if present := [x for x in spacers if x in sanitized_mac]:
            for x in present:
                sanitized_mac = mac.replace(x, "")

        if len(sanitized_mac) > 12:
            logger.debug(f"Invalid mac: {sanitized_mac}")
            return

        sanitized_mac = sanitized_mac.lower()

        frame: bytes = bytes.fromhex("FF" * 6 + sanitized_mac * 16)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(frame, ("255.255.255.255", 7))
    except Exception:
        logger.exception(f"Failed to send magic packet for {sanitized_mac}")
        raise ServiceError("faileed to send magic packet")
