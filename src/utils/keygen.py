import secrets


class KeyGenerator:
    """
    Generates unique, short, identifier strings (Crockford base32).
    Ensures uniqueness by checking against existing keys.
    """

    ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
    keys: set[str] = set()
    _initialized: bool = False

    def __init__(self, length: int = 4) -> None:
        """
        Initializes the generator.

        Args:
            length: The length of the generated key.
        """
        if length <= 0 or length > 63:
            raise ValueError("length must be between 1 and 63")
        self.length = length


    @classmethod
    def load(cls, used_keys: list[str]) -> None:
        """
        Loads already used keys.

        Args:
            used_keys: Already used keys.
        """
        if not KeyGenerator._initialized:
            for key in used_keys:
                KeyGenerator.keys.add(key)
            KeyGenerator._initialized = True
        

    def gen(self) -> str:
        """
        Generate a `length` character long string, in Crockford base32.
        
        Returns:
            key: Generated, unique key.

        Raises:
            RuntimeError: If KeyGenerator was not initialized.
        """
        
        if not KeyGenerator._initialized:
            raise RuntimeError(f"KeyGenerator is not initialized")
        
        while True:
            new = ''.join(secrets.choice(self.ALPHABET) for _ in range(self.length))
            if new not  in KeyGenerator.keys:
                KeyGenerator.keys.add(new)
                return new