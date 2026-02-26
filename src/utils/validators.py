import re
from pathlib import Path
from .keygen import KeyGenerator


def validate_linux_user(v: str) -> str:
    """Validates Linux username format."""
    pattern = r"^[a-z_][a-z0-9_-]*$"
    if not re.match(pattern, v):
        raise ValueError('Invalid Linux username')
    return v


def validate_absolute_path(v: Path) -> Path:
    """Validates if path is absolute and has safe format."""
    if not v.is_absolute():
        raise ValueError('Path must be absolute')
    
    # Basic sanitization check for path traversal or dangerous characters
    # Allow alphanumeric, /, _, -, .
    s = str(v)
    pattern = r"^/[\w\-\./]+$"
    if not re.match(pattern, s) or '..' in s:
        raise ValueError('Invalid path format or characters')
    return v


def validate_subdomain(v: str) -> str:
    """Validates subdomain using KeyGenerator rules."""
    if KeyGenerator.validate(v):
        return v
    raise ValueError('Subdomain contains illegal characters')


def check_path_user_consistency(user: str | None, path: Path | None) -> None:
    """Ensures that paths in /home/ match the specified username."""
    if not user or not path:
        return
    
    parts = path.parts
    # parts: ('/', 'home', 'user', ...)
    if len(parts) >= 3 and parts[1] == 'home':
        home_user = parts[2]
        if home_user != user:
            raise ValueError(f"Path in /home/ must match user '{user}', but found '{home_user}'")


def validate_ram_allocation(v: str) -> str:
    """Validates RAM allocation string (e.g., '2G', '4096M')."""
    amount = int(v[:-1])
    size = v[-1]

    if size not in ["M", "G"]:
        raise ValueError(f"Choose from [M, G]")
    
    if size == "M" and (amount > 6135 or amount < 2048)  or size == "G" and (amount > 8 or amount < 2):
        raise ValueError(f"RAM amount has to be between 2 and 6 GB")
    
    return v