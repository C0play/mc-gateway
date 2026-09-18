import socket
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from src.api.data.models.host import HostConfig
from src.utils.wake import send_magic_packet

from ..exceptions.errors import ServiceError


class BaseHost(ABC):
    def __init__(self, ip: str, mac: str, config: HostConfig) -> None:
        self.ip = ip
        self.mac = mac
        self.config = config
        self.on_start: Callable[[BaseHost], None] | None = None

    @abstractmethod
    def is_online(self) -> bool:
        """
        Checks if the host is reachable.

        Returns:
            bool: True if the host is online and reachable.
        """
        ...

    @abstractmethod
    def is_starting(self) -> bool:
        """
        Checks if the host is currently in the process of waking up.

        Returns:
            bool: True if a start operation is in progress.
        """
        ...

    @abstractmethod
    def start(self):
        """
        Initiates the host startup sequence.

        Returns:
            bool: True if the host is online.

        Raises:
            TimeoutError: If the host fails to become online within the expected time.
            ServiceError: If the start command fails.
        """
        ...

    @abstractmethod
    def dict(self) -> dict[str, str]:
        """Returns host parameters as a python dictionary."""

    def register_callback(self, on_start: Callable[["BaseHost"], None]) -> None:
        if self.on_start:
            return
        self.on_start = on_start

    def __str__(self) -> str:
        return f"Host({self.ip})"

    def __hash__(self) -> int:
        return hash(self.ip)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseHost):
            return False
        return self.ip == other.ip


class ControllerHost(BaseHost):
    def __init__(self, ip: str, mac: str, config: HostConfig) -> None:
        super().__init__(ip, mac, config)

        self._start_lock = threading.Lock()
        self._stop_lock = threading.Lock()

    def is_online(self) -> bool:
        try:
            with socket.create_connection((self.ip, 22), timeout=0.5):
                return True
        except ConnectionRefusedError:
            return True
        except OSError:
            return False

    def is_starting(self) -> bool:
        if self._start_lock.acquire(blocking=False):
            self._start_lock.release()
            return False
        return True

    def start(self):
        try:
            with self._start_lock:
                if self.is_online():
                    return

                send_magic_packet(self.mac)

                attempts, wait_time = 6, 10
                for _ in range(attempts):
                    if self.is_online():
                        return
                    time.sleep(wait_time)

                raise TimeoutError(
                    f"host {self.ip} was offline after {attempts * wait_time}s"
                )
        except ServiceError as e:
            raise ServiceError(f"host {self.ip} start failed: {e}")

    def dict(self) -> dict[str, str]:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "config": self.config.model_dump_json(indent=2),
        }

    def _execute_on_start(self) -> None:
        if not self.on_start:
            return
        callback = self.on_start
        self.on_start = None
        callback(self)
