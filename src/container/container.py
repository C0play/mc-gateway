import time
import threading
import subprocess
from abc import ABC, abstractmethod
from typing import Callable, cast

from ..host.host import BaseHost, SSHHost
from ..utils.logger import logger



class BaseContainer(ABC):
    
    def __init__(self, subdomain: str, port: int, host: BaseHost) -> None:
        self.subdomain = subdomain
        self.port = port
        self.host = host


    @abstractmethod
    def is_online(self) -> bool:
        """
        Checks if the container is currently running.

        Returns:
            bool: True if the container is running and responsive, False otherwise.
        """
        ...

    @abstractmethod
    def is_starting(self) -> bool:
        """
        Checks if the container is currently in the process of starting up.
        This is used to prevent multiple start commands from being issued simultaneously.

        Returns:
            bool: True if a start operation is in progress.
        """
        ...

    @abstractmethod
    def start(self) -> bool:
        """
        Initiates the container startup sequence.
        Handles host startup if necessary.

        Returns:
            bool: True if the container started successfully or was already running.
        
        Raises:
            TimeoutError: If the container fails to become online within the expected time.
            RuntimeError: If the start command fails.
        """
        ...

    @abstractmethod
    def stop(self) -> bool:
        """
        Initiates the container shutdown sequence.

        Returns:
            bool: True if the container stopped successfully or was already stopped.
            
        Raises:
            TimeoutError: If the container fails to stop within the expected time.
            RuntimeError: If the stop command fails.
        """
        ...

    def dict(self) -> dict[str, str]:
        """
        Returns a dictionary representation of the container's connection parameters.

        Returns:
             dict[str, str]: Dictionary containing 'ip' and 'port'.
        """
        return {
            "ip": self.host.ip,  
            "port": str(self.port)
        }

    def __str__(self) -> str:
        return f"Container({self.subdomain})"
    
    def __repr__(self) -> str:
        return f"Container<{self.subdomain}>"
    
    def __hash__(self) -> int:
        return hash(self.subdomain)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseContainer):
            return False
        return self.subdomain == other.subdomain



class SSHContainer(BaseContainer):
    """
    A container implementation that manages a Docker container on a remote host via SSH.
    """

    def __init__(
            self, subdomain: str, port: int, host: SSHHost,
            deploy: Callable[..., None] | None = None,
    ) -> None:
        """
        Initializes the SSHContainer.

        Args:
            deploy: If provided, called on first start to deploy the container
                    (e.g. write compose.yml and mark as initialized). If None,
                    the container is assumed to already be deployed.
        """
        
        super().__init__(subdomain, port, host)
        self.host = cast(SSHHost, self.host)
        
        self.path = self._generate_path(host.path, port)
        self.name = self._generate_name(port)

        self._deploy_fn = deploy
        self._start_lock = threading.Lock()
        self._stop_lock = threading.Lock()


    def is_online(self) -> bool:
        """
        Implementation using `docker inspect` via SSH.
        """
        if not self.host.is_online():
            return False
        try:
            cmd = ["ssh", f"{self.host.user}@{self.host.ip}", "docker", "inspect", "-f", "{{.State.Running}}", self.name]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            # logger.debug(f"container.is_online inspect: rc={res.returncode} stderr={res.stderr.strip()} stdout={res.stdout.strip()}")
            
            return res.returncode == 0 and res.stdout.strip().lower() == "true"

        except subprocess.TimeoutExpired as e:
            return False
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"docker inspect failed for {self.subdomain}: {e}")
        except Exception as e:
            raise RuntimeError(f"{self.subdomain} status check failed: {e}")


    def is_starting(self) -> bool:
        """
        Checks local lock to determine if start is in progress.
        """
        if self._start_lock.acquire(blocking=False):
            self._start_lock.release()
            return False
        return True
    

    def start(self) -> bool:
        try:
            with self._start_lock:
                if not self.host.is_online():
                    if not self.host.start():
                        return False
                
                self._deploy()

                if self.is_online():
                    return True

                cmd = ["ssh", f"{self.host.user}@{self.host.ip}", "docker", "compose", "-f", self.path + "/compose.yml", "up", "-d"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                logger.info(f"starting container {self.name} on {self.host.ip}:{self.port} (rc={res.returncode})")

                attempts, wait_time = 6, 10
                for _ in range(attempts):
                    time.sleep(wait_time)
                    if self.is_online():
                        return True
                    
                raise TimeoutError(attempts * wait_time)
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"compose up timed out for {self.subdomain}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"compose up failed for {self.subdomain}: {e}" + e.stdout + e.stderr)
        except TimeoutError as e:
            raise TimeoutError(f"{self.subdomain} was offline after {e.args[0]}s")
        except Exception as e:
            raise RuntimeError(f"{self.subdomain} start failed: {e}")
        

    def stop(self) -> bool:
        try:
            with self._stop_lock:
                if not self.is_online():
                    return True

                cmd = ["ssh", f"{self.host.user}@{self.host.ip}", "docker", "compose", "-f", self.path + "/compose.yml", "down"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                logger.info(f"stopping container {self.name} on {self.host.ip}:{self.port} (rc={res.returncode})")
                
                attempts, wait_time = 20, 3
                for _ in range(attempts):
                    time.sleep(wait_time)
                    if not self.is_online():
                        logger.info(f"stopped container {self.name} on {self.host.ip}:{self.port}")
                        return True
                
                raise TimeoutError(attempts * wait_time)
        
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"docker compose down failed for {self.subdomain}: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"compose down timed out for {self.subdomain}")
        except TimeoutError as e:
            raise TimeoutError(f"{self.subdomain} online after {e.args[0]}s ")
        except Exception as e:
            raise RuntimeError(f"{self.subdomain} stop failed: {e}")

    
    def _deploy(self) -> None:
        """Call deploy callback on first start if not yet initialized."""

        if self._deploy_fn is None:
            logger.debug(f"container {self.subdomain} already deployed")
            return
        
        logger.info(f"Initializing {self.subdomain}: deploying compose.yml to {self.host.ip}")
        try:
            self._deploy_fn()
        except Exception as e:
            logger.error(f"deployment of {self.subdomain} failed {e}")
        else:
            logger.info(f"deployment of {self.subdomain} succeeded")
            self._deploy_fn = None


    @staticmethod
    def _generate_path(host_path: str, port: int) -> str:
        return f"{host_path}/server_{port}"


    @staticmethod
    def _generate_name(port: int) -> str:
        return f"mc_{port}"