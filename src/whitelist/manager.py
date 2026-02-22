from abc import ABC, abstractmethod
from .repository import BaseWhitelistRepository


class BaseWhitelistManager(ABC):
    """A base class for managing and validating whitelisted players"""

    @abstractmethod
    def __init__(self, whitelistRepo: BaseWhitelistRepository) -> None:
        self.storage = whitelistRepo

    @abstractmethod
    def validate(self, subdomain: str | None = None, username: str | None = None) -> bool:
        """
        Checks if a player is whitelisted on a specific server or globally.

        Args:
            subdomain: The subdomain of the server (optional if checking generally).
            username: The player's username (optional if checking generally).

        Returns:
            bool: True if the combination exists in the whitelist, False otherwise.
        """
        ...
        
    @abstractmethod
    def dict(self) -> list[dict[str, list[str]]]:
        """
        Returns whitelist contents.

        Returns:
            list[dict[str, list[str]]]: List of user-subdomains mappings.
        """
        ...


class WhitelistManager(BaseWhitelistManager):

    def __init__(self, whitelistRepo: BaseWhitelistRepository) -> None:
        self.storage = whitelistRepo
        

    def validate(self, subdomain: str | None = None, username: str | None = None) -> bool:
        if username and subdomain:
            return self.storage.exists({"username": username, "subdomain": subdomain})
        elif username:
            return self.storage.exists({"username": username})
        elif subdomain:
            return self.storage.exists({"subdomain": subdomain})
        else:
            return False


    def dict(self) -> list[dict[str, list[str]]]:
        return self.storage.list()