from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig():
    name: str
    user: str
    password: str
    host: str
    port: int


@dataclass(frozen=True)
class PathConfig():
    containers_file_path: str
    whitelist_file_path: str
    hosts_file_path: str


@dataclass(frozen=True)
class ServerConfig():
    ip: str
    port: int
    control_port: int
    max_clients: int
    domain: str


@dataclass(frozen=True)
class ShutdownConfig():
    container_idle_timeout: int


@dataclass(frozen=True)
class StorageConfig():
    storage: PostgresConfig | PathConfig

@dataclass(frozen=True)
class Config():
    server: ServerConfig
    shutdown: ShutdownConfig
    storage: StorageConfig


class ConfigException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)