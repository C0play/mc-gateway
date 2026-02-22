from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig():
    """Configuration for PostgreSQL database connection."""
    name: str
    user: str
    password: str
    host: str
    port: int


@dataclass(frozen=True)
class StorageConfig():
    """Wrapper for storage-related configurations."""
    storage: PostgresConfig


@dataclass(frozen=True)
class ServerConfig():
    """Configuration for the proxy server and control socket."""
    ip: str
    port: int
    control_port: int
    max_clients: int
    domain: str


@dataclass(frozen=True)
class ShutdownConfig():
    """Configuration for automatic shutdown behavior."""
    container_idle_timeout: int


@dataclass(frozen=True)
class Config():
    """Main configuration aggregation class."""
    server: ServerConfig
    shutdown: ShutdownConfig
    storage: StorageConfig


class ConfigException(Exception):
    """Exception raised for configuration loading errors."""
    def __init__(self, *args: object) -> None:
        super().__init__(*args)