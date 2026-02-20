import time
import threading
import subprocess
from abc import ABC, abstractmethod

from ..host.host import BaseHost
from ..utils.logger import logger



class BaseContainer(ABC):
    
    def __init__(self, subdomain: str, port: int, host: BaseHost) -> None:
        self.subdomain = subdomain
        self.port = port
        self.host = host


    @abstractmethod
    def is_online(self) -> bool:
        """Check if the container is online"""
        ...

    @abstractmethod
    def is_starting(self) -> bool:
        """Check if container startup was initiated"""
        ...

    @abstractmethod
    def start(self) -> bool:
        """Start the container"""
        ...

    @abstractmethod
    def stop(self) -> bool:
        """Stop the container"""
        ...

    def dict(self) -> dict[str, str]:
        """Return container params as a dict"""
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

    def __init__(self, subdomain: str, port: int, host: BaseHost) -> None:
        super().__init__(subdomain, port, host)
        
        self.path: str = f"{self.host.path}/server_{port}"
        self.name: str = f"mc_{port}"

        self._start_lock = threading.Lock()
        self._stop_lock = threading.Lock()


    def is_online(self) -> bool:
        if not self.host.is_online():
            return False
        try:
            cmd = ["ssh", f"{self.host.user}@{self.host.ip}", "docker", "inspect", "-f", "{{.State.Running}}", self.name]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            logger.debug(f"container.is_online inspect: rc={res.returncode} stderr={res.stderr.strip()} stdout={res.stdout.strip()}")
            
            return res.returncode == 0 and res.stdout.strip().lower() == "true"

        except subprocess.TimeoutExpired as e:
            return False
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"docker inspect failed for {self.subdomain}: {e}")
        except Exception as e:
            raise RuntimeError(f"{self.subdomain} status check failed: {e}")


    def is_starting(self) -> bool:
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
                
                attempts, wait_time = 6, 10
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