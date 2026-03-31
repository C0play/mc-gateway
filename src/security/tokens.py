import secrets


def generate_token_bytes(nbytes: int) -> bytes:
    return secrets.token_bytes(nbytes=nbytes)


def generate_token_urlsafe(nbytes: int) -> str:
    return secrets.token_urlsafe(nbytes=nbytes)
