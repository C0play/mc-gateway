import secrets
from .models import Container


class KeyGenerator:
    """
    Generates unique, short, identifier strings (Crockford base32).
    Ensures uniqueness by checking against existing subdomains in standard database mode.
    """

    ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
    keys: set[str] = set()
    _initialized: bool = False

    def __init__(self, length: int = 4) -> None:
        """
        Initializes the generator. Loads existing keys from the Container table on first run.

        Args:
            length: The length of the generated key.
        """
        if length <= 0 or length > 63:
            raise ValueError("length must be between 1 and 63")
        self.length = length

        if not KeyGenerator._initialized:
            query = Container.select(Container.subdomain)
            for container in query:
                KeyGenerator.keys.add(container.subdomain)
            KeyGenerator._initialized = True


    def gen(self) -> str:
        """Generate a [length] character long string, in Crockford base32."""
        
        while True:
            new = ''.join(secrets.choice(self.ALPHABET) for _ in range(self.length))
            if new not  in KeyGenerator.keys:
                KeyGenerator.keys.add(new)
                return new