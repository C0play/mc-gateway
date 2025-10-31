import csv
import socket
import threading
from enum import IntEnum

class state(IntEnum):
    Null = 0
    Status = 1
    Login = 2
    Transfer = 3

class Whitelist():

    def __init__(self, file_name: str) -> None:

        self._list_lock = threading.Lock()
        self._list: dict[str, tuple[str, int]] = {}
        self._file_name = file_name
        self._load(file_name)

    def _load(self, file_name: str):
        try:
            with  self._list_lock, open("allow_list.csv") as allow_list:
                reader = csv.reader(allow_list)
                for row in reader:
                    name, ip, port = row
                    self._list.setdefault(name, (ip, int(port)))
        
        except FileNotFoundError:
            print(f"ERROR: {file_name} not found, continuing with empty allow list")
        except Exception as e:
            raise RuntimeError(f"whitelist configuration failed")
    
    def add(self, username: str, ip: str, port: int) -> bool:
        try:
            with self._list_lock:
                if username in self._list:
                    if self._list[username] == (ip, port):
                        self._list.update({username: (ip, port)})
                else:
                    self._list.setdefault(username, (ip, port))
        
            with open(self._file_name, mode='a') as allow_list:
                writer = csv.writer(allow_list)
                writer.writerow([username, port])

            return True
        except ValueError as e:
            return False

    def remove(self, username: str) -> bool:
        file_backup = None
        try: 
            with open(self._file_name, "rb") as backup:
                file_backup = backup.read()
        except Exception as e:
            raise RuntimeError(f"backup creation failed, removal aborted {e}")

        try:
            with self._list_lock:
                self._list.pop(username)
        
            valid_rows = []
            with open(self._file_name, mode='r') as allow_list_old:
                reader = csv.reader(allow_list_old)
                for row in reader:
                    if row[0] != username:
                        valid_rows.append(row)
            
            with open(self._file_name, mode='w') as allow_list_new:
                writer = csv.writer(allow_list_new)
                for row in valid_rows:
                    writer.writerow(row)

            return True
        except Exception as e:
            if not file_backup:
                raise RuntimeError("critical error while removing a whitelist entry: " + \
                                   f"removal failed and backup is None {e}")
            try:
                with open(self._file_name, "wb") as a:
                    a.write(file_backup)
            except Exception as e:
                raise RuntimeError(f"critical error while restoring whitelist file from backup: " + \
                                   f"writing backup to file failed: {e}")
            return False


    def __getitem__(self, item: str):
        with self._list_lock:
            return self._list[item]
        
    def __str__(self) -> str:
        temp = ''
        for name, (ip, port) in self._list.items():
            temp += f"{name}, {ip}, {port}\n"
        return temp  

    def __repr__(self) -> str:
        temp = ''
        for name, (ip, port) in self._list.items():
            temp += f"{name}, {ip}, {port}\n"
        return temp
    
    def __contains__(self, key: str):
        return key in self._list
    
    def to_dict(self) -> dict[str, dict[str, str | int]]:
        with self._list_lock:
            return {
                username: {"ip": ip, "port": port}
                for username, (ip, port) in self._list.items()
            }


class Client():
    _config_loaded: bool = False
    _whitelist_file_name: str | None = None
    whitelist: Whitelist

    @classmethod
    def load_config(cls, file_name: str | None = None):
        try:
            if cls._config_loaded:
                return
            cls._config_loaded = True
            if cls._whitelist_file_name:
                cls.whitelist = Whitelist(cls._whitelist_file_name)
            elif file_name:
                cls.whitelist = Whitelist(file_name)
            else:
                raise ValueError("whitelist file name is not set and none was provided")
        except Exception as e:
            raise RuntimeError(f"client configuration failed to load: {e}")


    def __init__(self, client_socket: socket.socket, addr: tuple[str, int]) -> None:
        Client.load_config()
        self.socket = client_socket
        self.ip = addr[0]
        self.port = addr[1]
        self.state = state.Null

    def updateState(self, newState: int)  -> None:
        self.state = newState

    def close(self):
        try:
            self.socket.close()
        except Exception as e:
            raise RuntimeError(f"LOG: {self} closing client {e}")
    
    @classmethod
    def validate(cls, username: str) -> tuple[str | None, int | None]:
        Client.load_config()
        if username not in cls.whitelist:
            return None, None
            
        ip, port = cls.whitelist[username]
        return ip, port

    def __eq__(self, other) -> bool:
        if not isinstance(other, Client):
            return False
        return self.port == other.port if self.ip == other.ip else False
    
    def __hash__(self) -> int:
        return hash((self.ip, self.port))
    
    def __repr__(self) -> str:
        return f"Client<ip={self.ip}, port={self.port}>"
    
    def __str__(self) -> str:
        return f"Client<{self.ip}, {self.port}>"

