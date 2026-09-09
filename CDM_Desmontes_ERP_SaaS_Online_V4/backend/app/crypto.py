import base64
import hashlib
import os
from cryptography.fernet import Fernet


def _fernet():
    raw = os.getenv("APP_ENCRYPTION_KEY", "").strip()
    if raw:
        key = raw.encode()
    else:
        # Development-safe deterministic key. Set APP_ENCRYPTION_KEY in production.
        seed = os.getenv("SECRET_KEY", "CHANGE_THIS_SECRET_IN_PRODUCTION").encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(key)


def encrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except Exception:
        return ""
