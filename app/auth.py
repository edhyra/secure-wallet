"""Authentication helpers: password hashing and verification."""

from passlib.context import CryptContext

# Use pbkdf2_sha256 to avoid relying on the bcrypt backend (no 72-byte limit).
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)
