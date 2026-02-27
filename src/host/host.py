import os
import time
import socket
import tempfile
import threading
import subprocess
from subprocess import CalledProcessError
from abc import ABC, abstractmethod
from typing import Callable

from ..utils.logger import logger


class BaseHost(ABC):
    
    def __init__(self, ip: str, mac: str) -> None:
        self.ip = ip
        self.mac = mac
        self.on_start: Callable[['BaseHost'], None] | None = None


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
    def start(self) -> bool:
        """
        Initiates the host startup sequence.
        
        Returns:
            bool: True if the host is online.

        Raises:
            TimeoutError: If the host fails to become online within the expected time.
            RuntimeError: If the start command fails.
        """
        ...
    
    @abstractmethod
    def stop(self) -> bool:
        """
        Initiates the host shutdown sequence.

        Returns:
            bool: True if the host was shut down successfully.

        Raises:
            TimeoutError: If the host fails to stop within the expected time.
            RuntimeError: If the stop command fails.
        """
        ...
    
    @abstractmethod
    def deploy(self, mc_port: int, config: str) -> None:
        """
        Deploys container configuration for the given Minecraft port.

        Args:
            mc_port: The Minecraft port number identifying the container.
            config: Text content of the configuration to deploy.

        Raises:
            RuntimeError: If deployment fails.
        """
        ...
    
    @abstractmethod
    def remove(self, mc_port: int) -> None:
        """
        Removes the container identified by the Minecraft port from the host.

        Args:
            mc_port: The port number identifying the container.

        Raises:
            RuntimeError: If removal fails.
        """
        ...
    
    def dict(self) -> dict[str, str]:
        """
        Returns host parameters as a dictionary.

        Returns:
            dict[str, str]: Dictionary containing all host parameters.
        """
        return {
            "ip": self.ip,
            "mac": self.mac,
        }
    
    def register_callback(self, on_start: Callable[['BaseHost'], None]) -> None:
        if self.on_start:
            return 
        self.on_start = on_start

    def __str__(self) -> str:
        return f"Host({self.ip})"
    
    def __repr__(self) -> str:
        return f"Host<{self.ip}>"
    
    def __hash__(self) -> int:
        return hash(self.ip)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseHost):
            return False
        return self.ip == other.ip


class SSHHost(BaseHost):
    """
    A host implementation that manages a remote machine via SSH and Wake-on-LAN.
    """

    def __init__(self, ip: str, mac: str, user: str, path: str) -> None:
        super().__init__(ip, mac)
        self.user = user
        self.path = path

        self._start_lock = threading.Lock()
        self._stop_lock = threading.Lock()


    def is_online(self) -> bool:
        """
        Checks connectivity via TCP/22 (SSH).
        """
        try:
            with socket.create_connection((self.ip, 22), timeout=0.5):
                self._execute_on_start()
                return True
        except OSError:
            return False


    def is_starting(self) -> bool:
        """
        Checks local lock to determine if wake-up is in progress.
        """
        if self._start_lock.acquire(blocking=False):
            self._start_lock.release()
            return False
        return True


    def start(self) -> bool:
        """
        Uses `wakeonlan` magic packet and waits for SSH port availability.
        """
        try:
            with self._start_lock:
                if self.is_online():
                    return True

                cmd = ["wakeonlan", self.mac]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=0.1)

                attempts, wait_time = 6, 10
                for _ in range(attempts):
                    if self.is_online():
                        return True
                    time.sleep(wait_time)

                raise TimeoutError(attempts * wait_time)
        except TimeoutError as e:
            raise TimeoutError(f"host {self.ip} was offline after {e.args[0]}s")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"host {self.ip} wake command failed with code: {e.returncode}")
        except Exception as e:
            raise RuntimeError(f"host {self.ip} start failed: {e}")


    def stop(self) -> bool:
        """
        Initiates the host shutdown sequence via SSH command.
        """
        try:
            with self._stop_lock:
                if not self.is_online():
                    return True

                cmd = ["ssh", f"{self.user}@{self.ip}", "sudo", "shutdown", "-h", "now"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                logger.debug(f"Host {self.ip} shutdown stderr: {(res.stderr or '').strip()}")
                if res.returncode == 0:
                    logger.info("Host %s shutdown command succeeded", self.ip)
                else:
                    logger.warning("Host %s shutdown command failed with code %s", self.ip, res.returncode)
                    
                if res.returncode != 0:
                    raise RuntimeError(res.stdout, res.stderr)

                attempts, wait_time = 6, 10
                for _ in range(attempts):
                    if not self.is_online():
                        return True
                    time.sleep(wait_time)

                raise TimeoutError(attempts * wait_time)
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"host {self.ip} shutdown command timed out")
        except TimeoutError as e:
            raise TimeoutError(f"host {self.ip} offline after {e.args[0]}s")
        except Exception as e:
            raise RuntimeError(f"host {self.ip} stop failed: {e}")
        
    
    def deploy(self, mc_port: int, config: str) -> None:
        """
        Creates the container directory if needed and writes compose.yml via SCP.
        """
        
        path = f"{self.path}/server_{mc_port}"
        filepath = path + "/compose.yml"
        dir_exists = False
        mkdir_cmd = ["ssh", f"{self.user}@{self.ip}", "mkdir", "-p", path]
        logger.debug(mkdir_cmd)
        try: 
            subprocess.run(mkdir_cmd, capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            if "File exists" not in e.output: 
                raise RuntimeError(f"failed to create directory {path} on {self.ip}: {e}")
            dir_exists = True
        except Exception as e:
            raise RuntimeError(e)

        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                tmp.write(config)
                tmp_path = tmp.name
        except Exception as e:
            raise RuntimeError(f"writing tempfile for {path} failed: {e}")
        
        try:
            scp_cmd = ["scp", tmp_path, f"{self.user}@{self.ip}:{filepath}"]
            subprocess.run(scp_cmd, capture_output=True, text=True, check=True)
        except Exception as e:
            if not dir_exists:
                rmdir_cmd = ["ssh", f"{self.user}@{self.ip}", "rmdir", path]
                subprocess.run(rmdir_cmd, capture_output=True, text=True, check=True)
            raise RuntimeError(f"failed to transfer {filepath} to {self.ip}: {e}")
        finally:
            os.unlink(tmp_path)


    def remove(self, mc_port: int) -> None:
        """Removes the container directory via SSH rm -rf."""

        path = f"{self.path}/server_{mc_port}"
        check_cmd = ["ssh", f"{self.user}@{self.ip}", "test", "-d", path]
        res = subprocess.run(check_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.debug(f"remove: {path} does not exist on {self.ip}, skipping")
            return

        rmrf_cmd = ["ssh", f"{self.user}@{self.ip}", "rm", "-rf", path]
        try:
            subprocess.run(rmrf_cmd, capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            logger.debug(f"stdout: {e.stdout}, stderr: {e.stderr}")
            raise RuntimeError(f"failed to remove {path}: {e}")
        except Exception as e:
            raise RuntimeError(f"unexpected error during removal of {path}: {e}")


    def _execute_on_start(self) -> None:
        if not self.on_start:
            return
        callback = self.on_start
        self.on_start = None
        callback(self)


    def dict(self) -> dict[str, str]:
        return {
            **super().dict(),
             "path": self.path,
            "user": self.user,
        }