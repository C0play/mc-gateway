__all__ = [
    "AuthRouter",
    "ContainerRouter",
    "HostRouter",
    "ApiKeyRouter",
    "PlayerRouter",
    "SystemRouter",
    "UserRouter"
]

from .users import UserRouter
from .auth import AuthRouter
from .container import ContainerRouter
from .host import HostRouter
from .key import ApiKeyRouter
from .player import PlayerRouter
from .system import SystemRouter