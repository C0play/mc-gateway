import os
from ..utils.models import db_init
from .config import  (
    ServerConfig,
    ShutdownConfig,
    Config,
    ConfigException,
    PostgresConfig,
    StorageConfig
)



def _load_storage() -> StorageConfig:
    """
    Loads storage configuration from environment variables.

    Returns:
        StorageConfig: The loaded storage configuration.
    
    Raises:
        ConfigException: If any required environment variable is missing.
    """

    postgres_name = os.getenv("PG_NAME")
    postgres_user = os.getenv("PG_USER")
    postgres_password = os.getenv("PG_PASSWORD")
    postgres_host = os.getenv("PG_HOST")
    postgres_port = os.getenv("PG_PORT")
    rcon_key = os.getenv("RCON_KEY")
    if (postgres_name and postgres_user and postgres_password 
        and postgres_host and postgres_port and rcon_key):
        postgres = PostgresConfig(
            postgres_name,
            postgres_user,
            postgres_password,
            postgres_host,
            int(postgres_port)
        )
        db_init(postgres)
        return StorageConfig(postgres, rcon_key)

    raise ConfigException(f"failed to load storage configuration")


def load_config() -> Config:
    """
    Loads the configuration from environment variables.

    Returns:
        Config: The complete application configuration.

    Raises:
        ConfigException: If required environment variables are missing.
    """
    
    ip = os.getenv("SERVER_IP")
    port = os.getenv("SERVER_PORT")
    control_port = os.getenv("CTRL_PORT")
    max_clients = os.getenv("CLIENTS")
    domain = os.getenv("DOMAIN")
    if not (ip and port and control_port and max_clients and domain):
        raise ConfigException(f"At least one variable is None in ServerConfig")
    
    server = ServerConfig(
        ip,
        int(port),
        int(control_port),
        int(max_clients),
        domain
    )

    container_idle_timeout = os.getenv("CONT_IDLE_SEC")
    if not(container_idle_timeout):
        raise ConfigException(f"At least one variable is None in ShutdownConfig")

    shutdown = ShutdownConfig(
        int(container_idle_timeout),
    )

    storage = _load_storage()

    return Config(server, shutdown, storage)