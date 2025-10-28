import os
import csv
import time
import socket
import threading
import subprocess
from dotenv import load_dotenv

class Host():

    def __init__(self, mac: str, ip: str, user: str, path: str) -> None:
        self.mac = mac
        self.ip = ip
        self.user = user
        self.path = path

        self._start_lock = threading.Lock()
        self._stop_lock = threading.Lock()

        
    def __hash__(self) -> int:
        return hash(self.ip)
    

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Host):
            return False
        return self.ip == other.ip


    def is_online(self) -> bool:
        try:
            with socket.create_connection((self.ip, 22), timeout=0.5):
                return True
        except OSError as e:
            return False

    def is_starting(self) -> bool:
        if self._start_lock.acquire(blocking=False):
            self._start_lock.release()
            return False
        return True


    def start(self) -> bool:
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
            raise TimeoutError(f"host was offline after {e.args[0]}s")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"wake command failed with code: {e.returncode}")
        except Exception as e:
            raise RuntimeError(f"failed to start host {e}")

    def stop(self) -> bool:
        try:
            with self._stop_lock:
                if not self.is_online():
                    return True

                cmd = ["ssh", f"{self.user}@{self.ip}", "sudo", "shutdown", "-h", "now"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if res.returncode != 0:
                    raise RuntimeError(res.stdout, res.stderr)

                attempts, wait_time = 6, 10
                for _ in range(attempts):
                    if not self.is_online():
                        return True
                    time.sleep(wait_time)

                raise TimeoutError(attempts * wait_time)
        except subprocess.TimeoutExpired:
            raise TimeoutError("shutdown command timed out")
        except TimeoutError as e:
            raise TimeoutError(f"host offline after {e.args[0]}s ")
        except Exception as e:
            raise RuntimeError(f"failed to stop host: {e}")
        
class Container():

    _config_loaded: bool = False
    idle_timeout: int

    @classmethod
    def _load_config(cls):
        if cls._config_loaded:
            return
        cls._config_loaded = True
        
        load_dotenv(override=True)
        cls.idle_timeout = int(os.getenv("CONT_IDLE_SEC", "300"))


    def __init__(self, host: Host, port: int) -> None:
        self.host = host
        self.port: int = port

        self.path: str = f"{host.path}/server_{port}"
        self.name: str = f"mc_{port}"

        self._start_lock = threading.Lock()
        self._stop_lock = threading.Lock()


    def is_online(self) -> bool:
        if not self.host.is_online():
            return False
        try:
            cmd = ["ssh", f"{self.host.user}@{self.host.ip}", "docker", "inspect", "-f", "{{.State.Running}}", self.name]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            # print(f"DEBUG: container is_online res: {res.stdout}")
            if res.returncode == 0 and res.stdout.strip().lower() == "true":
                return True
            return False

        except subprocess.TimeoutExpired as e:
            return False
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"docker inspect failed: {e}")
        except Exception as e:
            raise RuntimeError(f"container status check failed: {e}")

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

                attempts, wait_time = 6, 10
                for _ in range(attempts):
                    if self.is_online():
                        return True
                    time.sleep(wait_time)
                raise TimeoutError(attempts * wait_time)
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"compose up timed out")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"compose up failed: {e}" + e.stdout + e.stderr)
        except TimeoutError as e:
            raise TimeoutError(f"container was offline after {e.args[0]}s")
        except Exception as e:
            raise RuntimeError(f"container start failed: {e}")
        
    def stop(self):
        try:
            with self._stop_lock:
                if not self.is_online():
                    return True

                cmd = ["ssh", f"{self.host.user}@{self.host.ip}", "docker", "compose", "-f", self.path + "/compose.yml", "down"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                # print(f"DEBUG: container stop res: {res.returncode}\n{res.stdout}\n{res.stderr}")
                attempts, wait_time = 6, 10
                for _ in range(attempts):
                    if not self.is_online():
                        return True
                    time.sleep(wait_time)
                raise TimeoutError(attempts * wait_time)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"docker compose down failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("compose down timed out")
        except TimeoutError as e:
            raise TimeoutError(f"container online after {e.args[0]}s ")
        except Exception as e:
            raise RuntimeError(f"failed to stop container: {e}")


class Backend():

    def __init__(self, container: Container) -> None:
        self.container: Container = container

        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._is_connected: bool = False


    def is_connected(self):
        return self._is_connected
    
    
    def is_online(self):
        return self.container.is_online()


    def is_starting(self) -> bool:
        return self.container.is_starting()


    def start(self):
        try:
            if not self.container.is_online():
                if not self.container.start():
                    return False
        except Exception as e:
            raise RuntimeError(f"failed to prepare container {self.container.name}: {e}")


    def connect(self) -> None:
        try:
            if not self.container.host.is_online():
                raise RuntimeError(f"can not connect if host is offline")
            
            if not self.container.is_online():
                raise RuntimeError(f"can not connect if container is offline")
        
            attempts, wait_time = 6, 10
            for attempt in range(attempts):
                try:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.connect((self.container.host.ip, self.container.port))
                    self._is_connected = True
                    print(f"LOG: connected to backend on attempt {attempt + 1}")
                    return
                except (ConnectionRefusedError, OSError) as e:
                    self.socket.close()
                    print(f"LOG: backend connection attempt {attempt + 1} failed, retrying in 5s...")
                    time.sleep(wait_time)

            raise RuntimeError(f"connect failed after {attempts} attempts")
        except Exception as e:                
            raise RuntimeError(f"failed to connect: {e}")


    def disconnect(self) -> bool:
        try:
            self.socket.close()
            return True
        except Exception as e:
            raise RuntimeError(f"failed to close the connection: {e}")


class BackendPool():
    _config_loaded: bool = False
    
    _backends: dict[str, dict[int, tuple[Backend, float]]] = {} # ip -> {port -> (backend, last_used)}
    _backends_lock = threading.Lock()

    _hosts: dict[str, Host] = {} # ip -> Host

    @classmethod
    def _load_hosts(cls, hosts_file: str):
        with open(hosts_file) as hosts:
            reader = csv.reader(hosts)
            for row in reader:
                mac, ip, user, path = row
                cls._hosts.setdefault(ip, Host(mac, ip, user, path))


    def __init__(self, hosts_file: str, ) -> None:
        Container._load_config()
        BackendPool._load_hosts(hosts_file)

    
    @classmethod
    def get(cls, host_ip: str, container_port: int) -> Backend:
        try:
            with cls._backends_lock:
                if host_ip not in cls._backends:
                    host = cls._hosts[host_ip]
                    new_container = Container(host, container_port)
                    new_backend = Backend(new_container)
                    cls._backends.update({host_ip: {container_port: (new_backend, time.monotonic())}})
                else:
                    if container_port not in cls._backends[host_ip]:
                        host = cls._hosts[host_ip]
                        new_container = Container(host, container_port)
                        new_backend = Backend(new_container)
                        cls._backends[host_ip].update({container_port: (new_backend, time.monotonic())})
                    else:
                        backend, _ = cls._backends[host_ip][container_port]
                        cls._backends[host_ip][container_port] = (backend, time.monotonic())
                
                return cls._backends[host_ip][container_port][0]

        except Exception as e:
            raise RuntimeError(f"failed to get backend: {e}")


    @classmethod
    def update_timestamp(cls, ip: str, port: int):
        with cls._backends_lock:
            if ip in cls._backends and port in cls._backends[ip]:
                backend, _= cls._backends[ip][port]
                cls._backends[ip][port] = (backend, time.monotonic())


    @classmethod
    def cleanup_idle(cls) -> None:
        while True:
            time.sleep(5)
            curr_time = time.monotonic()
            to_be_deleted = []
            try:
                with cls._backends_lock:
                    for ip, _ in cls._backends.items():
                        for port, (backend, last_used) in cls._backends[ip].items():
                            if curr_time - last_used > backend.container.idle_timeout:
                                to_be_deleted.append((ip, port))
                    
                        if not cls._backends[ip] and cls._hosts[ip].is_online():
                            cls._hosts[ip].stop()
                            print(f"LOG: host {ip} was idle, shutting down")
                    
                    for ip, port in to_be_deleted:
                        cls._backends[ip][port][0].container.stop()
                        cls._backends[ip][port][0].disconnect()
                        del cls._backends[ip][port]
            except Exception as e:
                raise RuntimeError(f"shutting down container: {e}")