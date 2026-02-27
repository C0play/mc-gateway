from cryptography.fernet import Fernet


class CryptoProvider:
    """Provides encryption/decryption for sensitive data like RCON passwords."""
    
    _fernet: Fernet | None = None

    @classmethod
    def initialize(cls, key: str) -> None:
        """Initializes the Fernet instance with the provided key."""
        cls._fernet = Fernet(key.encode())


    @classmethod
    def _get_fernet(cls) -> Fernet:
        if cls._fernet is None:
            raise RuntimeError("CryptoProvider not initialized! Call initialize(key) first.")
        return cls._fernet


    @classmethod
    def encrypt(cls, plain_text: str) -> str:
        """Encrypts a string into a base64 encoded token."""
        return cls._get_fernet().encrypt(plain_text.encode()).decode()


    @classmethod
    def decrypt(cls, encrypted_token: str) -> str:
        """Decrypts a base64 encoded token back into plain text."""
        return cls._get_fernet().decrypt(encrypted_token.encode()).decode()
