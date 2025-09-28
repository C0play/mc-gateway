import time
import socket
import subprocess
from dotenv import dotenv_values

class Backend():
    config = dotenv_values(".env")

    ip = config["BACKEND_IP"]
    port = int(config["BACKEND_PORT"] or 25565)

    _mac = config["BACKEND_MAC"]
    _admin = config["ADMIN"]
    
    _status: bool = False

    def __init__(self, con : socket.socket) -> None:
        self.connection = con

    @classmethod
    def refresh_status(cls) -> None:
        if cls._backend_online():
            cls._status = cls._container_online()
        else:
            cls._status = False
    
    @classmethod
    def get_status(cls) -> bool:
        if cls._backend_online():
            cls._status = cls._container_online()
        else:
            cls._status = False
        
        return cls._status
        
    @classmethod
    def _backend_online(cls) -> bool:
        try:
            with socket.create_connection((cls.ip, 22), timeout=0.5):
                return True
        except OSError as e:
            print(f"DEBUG: backend_online: {e}")
            return False
    
    @classmethod
    def _container_online(cls) -> bool:
        if not cls._backend_online():
            return False
        
        cmd = ["ssh", f"{cls._admin}@{cls.ip}", "docker", "inspect", "-f", "{{.State.Running}}", "minecraft-mc-1"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip().lower() == "true":
            return True
        else:
            return False
        
    @classmethod
    def start(cls) -> bool:
        print("DEBUG: starting backend: ")
        cmd = ["wakeonlan", cls._mac]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=0.1)
            
            for _ in range(5):
                if cls._backend_online():
                    print(f"LOG: backend online")
                    return cls._container_start()
                else:
                    time.sleep(10)
            cls.refresh_status()
            return False
        except subprocess.TimeoutExpired:
            return False
        except subprocess.CalledProcessError:
            return False
    
    @classmethod
    def _container_start(cls) -> bool:
        if not cls._backend_online():
            return False
        cmd = ["ssh", f"{cls._admin}@{cls.ip}", "docker", "compose", "-f", "Minecraft/compose.yml", "up", "-d"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=4)
        for _ in range(5):
            if cls._container_online:
                cls.refresh_status()
                return True
            else:
                time.sleep(5)
        cls.refresh_status()
        return False
    
    @classmethod
    def shutdown(cls) -> bool:
        try:
            cmd = ["ssh", "blazej@server-pc", "sudo", "shutdown", "-h", "now"]
            res = subprocess.run(cmd, check=True, timeout=5)
            if res.returncode == 0:
                cls.refresh_status()
                return True
            else:
                cls.refresh_status()
                return False
        except:
            cls.refresh_status()
            return False
