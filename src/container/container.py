import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from json.decoder import JSONDecodeError
from typing import Any, Literal

import requests
from requests.exceptions import HTTPError

from src.api.data.models.container import ContainerConfig
from src.utils.logger import logger
from src.utils.rcon import RCON

from ..exceptions.errors import ServiceError
from ..host.host import BaseHost


class BaseContainer(ABC):
    @abstractmethod
    def __init__(self, *args) -> None:
        self.subdomain: str
        self.host: BaseHost
        self.mc_port: int

    @abstractmethod
    def is_online(self) -> bool:
        """
        Checks if the container is currently running.

        Returns:
            bool: True if the container is running and responsive, False otherwise.
        """

    @abstractmethod
    def is_starting(self) -> bool:
        """
        Checks if the container is currently in the process of starting up.
        This is used to prevent multiple start commands from being issued simultaneously.

        Returns:
            bool: True if a start operation is in progress.
        """

    @abstractmethod
    def start(self):
        """
        Initiates the container startup sequence. Handles host startup if necessary and deploys
        container configuration.

        Raises:
            TimeoutError: If the container fails to become online within the expected time.
            ServiceError: If the start command fails.
        """

    @abstractmethod
    def stop(self):
        """
        Initiates the container shutdown sequence.

        Raises:
            TimeoutError: If the container fails to stop within the expected time.
            ServiceError: If the stop command fails.
        """

    @abstractmethod
    def send_command(self, cmd: str):
        """
        Sends RCON command.

        Args:
            cmd (str): Command to be sent to the server.
        """

    @abstractmethod
    def dict(self) -> dict[str, str]:
        """
        Returns a dictionary representation of the container's connection parameters.

        Returns:
             dict[str, str]: Dictionary containing container parameters.
        """

    def __str__(self) -> str:
        return f"Container({self.subdomain})"

    def __hash__(self) -> int:
        return hash(self.subdomain)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseContainer):
            return False
        return self.subdomain == other.subdomain


class ControllerContainer(BaseContainer):
    STATUS_PATH = "/container/status/%d"
    STOP_PATH = "/container/stop/%d"
    START_PATH = "/container/start/%d"
    DEPLOY_PATH = "/container/create"
    DELETE_PATH = "/container/delete/%d"
    STATUS = Literal["starting", "online", "stopping", "offline"]
    TIMEOUT = 120

    def __init__(
        self,
        subdomain: str,
        host: BaseHost,
        authority: str,
        config: ContainerConfig,
    ) -> None:
        self.subdomain = subdomain
        self.host = host
        self.mc_port = config.mc_port
        self.authority = authority if authority[-1] != "/" else authority[:-1]
        self.config = config

        self.deploy_callback: Callable | None = None

        self.start_event = threading.Event()
        self.stop_event = threading.Event()
        self.create_event = threading.Event()
        self.delete_event = threading.Event()

    def is_online(self) -> bool:
        return (
            self.__request_task(
                "get",
                ControllerContainer.STATUS_PATH % self.mc_port,
            )["status"]
            == "online"
        )

    def is_starting(self) -> bool:
        return (
            self.__request_task(
                "get",
                ControllerContainer.STATUS_PATH % self.mc_port,
            )["status"]
            == "starting"
        )

    def start(self):

        if not (self.host.is_starting() or self.host.is_online()):
            self.host.start()

        if self.deploy_callback is not None:
            self.__deploy()
            self.deploy_callback()
            self.deploy_callback = None

        res = self.__request_task(
            "post",
            ControllerContainer.START_PATH % self.mc_port,
        )
        if not self.start_event.wait(timeout=ControllerContainer.TIMEOUT):
            raise TimeoutError(f"task {res['id']} timed out")
        self.start_event.clear()

    def stop(self):

        res = self.__request_task(
            "post",
            ControllerContainer.STOP_PATH % self.mc_port,
        )
        if not self.stop_event.wait(timeout=ControllerContainer.TIMEOUT):
            raise TimeoutError(f"task {res['id']} timed out")
        self.stop_event.clear()

    def delete(self):
        res = self.__request_task(
            "delete",
            ControllerContainer.DELETE_PATH % self.mc_port,
            body=self.config.model_dump(mode="json"),
        )

        if not self.delete_event.wait(timeout=ControllerContainer.TIMEOUT):
            raise TimeoutError(f"task {res['id']} timed out")
        self.delete_event.clear()

    def send_command(self, cmd: str) -> None:
        with RCON(
            self.host.ip,
            self.config.rcon_port,
            self.config.rcon_password,
        ) as rcon:
            if not rcon.login():
                logger.error(f"{self} RCON: authentication failed")
                return
            logger.info(f"{self}: RCON: /kick sent")
            rcon.send(cmd)

    def dict(self) -> dict[str, str]:
        return {
            "subdomain": self.subdomain,
            "host": self.host.ip,
        }

    def set_event(self, type: str):
        getattr(self, f"{type}_event").set()

    def __deploy(self):
        res = self.__request_task(
            "post",
            ControllerContainer.DEPLOY_PATH,
            body=self.config.model_dump(mode="json"),
        )

        if not self.create_event.wait(timeout=ControllerContainer.TIMEOUT):
            raise TimeoutError(f"task {res['id']} timed out")
        self.create_event.clear()

    def __request_task(
        self, method: str, path: str, body: dict | None = None
    ) -> dict[str, Any]:
        url = self.authority + path
        try:
            func = getattr(requests, method)
            resp = func(url=url, json=body)
            resp.raise_for_status()
            json = resp.json()

            if path.startswith(ControllerContainer.STATUS_PATH[:-2]):
                return json

            if json["status"] == "rejected":
                raise ServiceError(f"{self}: '{path.split('/')[2]}' task rejected")
            logger.debug(f"{self}: task '{path}' ({json['id']}) queued")

            return json
        except HTTPError as e:
            raise ServiceError(f"{self}: request failed {e}")
        except JSONDecodeError as e:
            raise ServiceError(f"{self}: can not decode content: {e} ")
