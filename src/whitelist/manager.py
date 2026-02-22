from .repository import BaseWhitelistRepository


class WhitelistManager():

    """A class for managing and validating whitelisted players"""
    def __init__(self, whitelistRepo: BaseWhitelistRepository) -> None:
        self.storage = whitelistRepo


    def validate(self, subdomain: str | None = None, username: str | None = None) -> bool:
        """If username is provided, check if player [username] is whitelisted on server [subdomain]"""
        if username and subdomain:
            return self.storage.exists({"username": username, "subdomain": subdomain})
        elif username:
            return self.storage.exists({"username": username})
        elif subdomain:
            return self.storage.exists({"subdomain": subdomain})
        else:
            return False


    def dict(self) -> list[dict[str, list[str]]]:
        """Returns whitelist contents in JSON friendly format"""
        return self.storage.dict()