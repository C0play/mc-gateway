import re
from pathlib import Path
from typing import TYPE_CHECKING

from ....utils.keygen import KeyGenerator

if TYPE_CHECKING:
    from .host import HostConfig
    from .container import ContainerConfig



def validate_linux_user(v: str) -> str:
    """Validates Linux username format."""
    
    pattern = r"^[a-z_][a-z0-9_-]*$"
    if not re.match(pattern, v):
        raise ValueError('Invalid Linux username')
    return v


def validate_absolute_path(v: str) -> str:
    """Validates if path is absolute and has safe format."""

    path = Path(v)
    if not path.is_absolute():
        raise ValueError('Path must be absolute')
    
    # Basic sanitization check for path traversal or dangerous characters
    # Allow alphanumeric, /, _, -, .
    pattern = r"^/[\w\-\./]+$"
    if not re.match(pattern, v) or '..' in v:
        raise ValueError('Invalid path format or characters')
    return v


def validate_subdomain(v: str) -> str:
    """Validates subdomain using KeyGenerator rules."""

    if KeyGenerator.validate(v):
        return v
    raise ValueError('Subdomain contains illegal characters')


def check_path_user_consistency(user: str | None, path: str | None) -> None:
    """Ensures that paths in /home/ match the specified username."""

    if not user or not path:
        return
    
    parts = path.split("/")
    if parts[0] == "":
        parts = parts[1:]
        
    # parts: ('home', 'user', ...)
    if parts[0] != "home" or parts[1] != user:
        raise ValueError(f"Path in /home/ must match user '{user}', but found '{parts[1]}'")


def validate_ram_format(v: str) -> str:
    """Validates RAM allocation string (e.g., '2G', '4096M')."""
    
    size = v[-1]

    if size not in ["M", "G"]:
        raise ValueError(f"Choose from [M, G]")
    
    return v


def to_Mb(ram: str) -> int:
    return int(ram[:-1]) * (1024 if ram[-1] == "G" else 1)


def validate_init_min_max_consistency(init: str | None, max: str | None) -> None:
    """
    Ensures that min < max.
    Implicitely calls validate_ram_format() for all parameters.
    """

    if not (init and max):
        return

    validate_ram_format(init)
    validate_ram_format(max)

    init_amount = to_Mb(init)
    max_amount = to_Mb(max)
    
    if not (init_amount < max_amount):
        raise ValueError(f"RAM values have to satisfy the ordering: init < max")
    

def validate_container_ram_against_host(host_cfg: "HostConfig", container_cfg: "ContainerConfig") -> None:
    """Ensure host.config.init_memory <= container.config.ram <= host.config.max_memory."""

    container_mb = to_Mb(container_cfg.ram)
    init_mb = to_Mb(host_cfg.init_memory)
    max_mb = to_Mb(host_cfg.max_memory)

    if not (init_mb <= container_mb <= max_mb):
        raise ValueError(
            f"container ram ({container_cfg.ram}) must satisfy "
            + f"{host_cfg.init_memory} <= ram <= {host_cfg.max_memory}"
        )
