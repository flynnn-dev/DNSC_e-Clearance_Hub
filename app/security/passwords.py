"""Password hashes. The plain password is never stored."""

import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_ROUNDS = 600_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ROUNDS)
    return f"{_ALGORITHM}${_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds_text, salt_hex, digest_hex = stored.split("$")
        rounds = int(rounds_text)
        salt = bytes.fromhex(salt_hex)
    except (AttributeError, TypeError, ValueError):
        return False
    if algorithm != _ALGORITHM or rounds < 1:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(digest.hex(), digest_hex)
