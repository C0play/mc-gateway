import os
import time
import socket
import subprocess
from dotenv import load_dotenv

class Backend():
    load_dotenv(override=True)
    ip = os.getenv("BACKEND_IP", "127.0.0.1")
    _mac = os.getenv("BACKEND_MAC", "00:00:00:00:00:00")
    _admin = os.getenv("ADMIN", "root")
    _status = False

    def __init__(self, port: int, container_directory: str, container_name: str) -> None:
        
        self.ctnr_port = port
        # minecraft-mc-1
        self.ctnr_name = container_name
        # Minecraft
        self.ctnr_dir = container_directory
        self._ctnr_status = False
        self._is_connected = False
        
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def open_connection(self):
        if self._is_connected:
            return
        
        if not Backend._backend_online():
            Backend._backend_start()
            if not Backend._backend_online():
                raise RuntimeError(f"failed to start host: {Backend.ip}")
        
        if not self._container_online():
            self.container_start()
            if not self._container_online():
                raise RuntimeError(f"failed to start container: {self.ctnr_name}")
        try:
            self.connection.connect((Backend.ip, self.ctnr_port))
            self._is_connected = True
        except Exception as e:
            self.connection.close()
            raise RuntimeError(f"connect failed: {e}")
        

    @classmethod
    def _backend_online(cls) -> bool:
        try:
            with socket.create_connection((cls.ip, 22), timeout=0.5):
                return True
        except OSError as e:
            print(f"DEBUG: backend_online: {e}")
            return False
    
    @classmethod
    def _backend_start(cls) -> bool:
        print("DEBUG: starting backend: ")
        if not Backend._backend_online():
            cmd = ["wakeonlan", Backend._mac]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=0.1)
        try:
            for _ in range(5):
                if Backend._backend_online():
                    print(f"LOG: backend online")
                    return True
                else:
                    time.sleep(10)
            return False
        except Exception:
            return False

    def get_ctnr_status(self) -> bool:
        self._refresh_ctnr_status()
        return self._ctnr_status
    
    def _refresh_ctnr_status(self) -> None:
        if Backend._backend_online():
            self._ctnr_status = self._container_online()
        else:
            self._ctnr_status = False
        
    def _container_online(self) -> bool:
        if not Backend._backend_online():
            return False
        
        cmd = ["ssh", f"{Backend._admin}@{Backend.ip}", "docker", "inspect", "-f", "{{.State.Running}}", f"{self.ctnr_name}"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip().lower() == "true":
            return True
        else:
            return False
        
    def container_start(self) -> bool:
        if not Backend._backend_start():
            return False
        
        cmd = ["ssh", f"{Backend._admin}@{Backend.ip}", "docker", "compose", "-f", f"{self.ctnr_dir}/compose.yml", "up", "-d"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=4)
        for _ in range(5):
            if self._container_online():
                self.ctnr_status = True
                return True
            else:
                time.sleep(5)
        self.ctnr_status = False
        return False