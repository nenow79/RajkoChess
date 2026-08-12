import hashlib
import secrets

from fastapi.concurrency import run_in_threadpool
from pwdlib import PasswordHash

PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("Rajko dummy password used only for timing")
COMMON_PASSWORDS = frozenset(
    {
        "passwordpassword",
        "password123456",
        "qwertyqwertyqwerty",
        "123456789012345",
        "rajko1234567890",
    }
)


def validate_password_strength(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Hasło musi mieć co najmniej 10 znaków")
    if len(password) > 128:
        raise ValueError("Hasło może mieć maksymalnie 128 znaków")
    if password.casefold() in COMMON_PASSWORDS:
        raise ValueError("To hasło jest zbyt łatwe do odgadnięcia")
    return password


async def hash_password(password: str) -> str:
    return await run_in_threadpool(PASSWORD_HASH.hash, password)


async def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    return await run_in_threadpool(
        PASSWORD_HASH.verify_and_update, password, password_hash
    )


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()
