import secrets


class KeyGenerator:

    ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
    keys: set[str] = set()

    def __init__(self, length: int = 4) -> None:
        if length <= 0 or length > 63:
            raise ValueError("length must be between 1 and 63")
        self.length = length


    def gen(self) -> str:
        """Generate a [length] character long string, in Crockford base32."""
        
        while True:
            new = ''.join(secrets.choice(self.ALPHABET) for _ in range(self.length))
            if new not  in KeyGenerator.keys:
                return new