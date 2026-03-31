from cryptography.fernet import Fernet


class Crypto:
    """Provides encryption/decryption for sensitive data like RCON passwords."""

    _fernet: Fernet | None = None

    @classmethod
    def initialize(cls, key: str) -> None:
        """Initialize Fernet with application key."""
        cls._fernet = Fernet(key.encode())

    @classmethod
    def _get_fernet(cls) -> Fernet:
        if cls._fernet is None:
            raise RuntimeError("Crypto not initialized. Call initialize(key) first.")
        return cls._fernet

    @classmethod
    def encrypt(cls, plain_text: str) -> str:
        return cls._get_fernet().encrypt(plain_text.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_token: str) -> str:
        return cls._get_fernet().decrypt(encrypted_token.encode()).decode()
