import hashlib

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str, salt: bytes) -> str:
    password_hash = hashlib.scrypt(
        password=password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    )
    return password_hash.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    computed_hash = hash_password(password, bytes.fromhex(salt_hex))
    return computed_hash == expected_hash_hex
