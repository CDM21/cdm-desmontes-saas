import base64
import hashlib
import os
from cryptography.fernet import Fernet

_DEFAULT_SECRET = "CHANGE_THIS_SECRET_IN_PRODUCTION"


def encryption_key_status():
    raw=(os.getenv("APP_ENCRYPTION_KEY") or "").strip()
    if raw:
        try:
            Fernet(raw.encode())
            valid=True
        except Exception:
            valid=False
        return {
            "configured": True,
            "valid": valid,
            "using_secret_fallback": False,
            "fallback_secret_default": False,
        }

    secret=os.getenv("SECRET_KEY",_DEFAULT_SECRET)
    return {
        "configured": False,
        "valid": False,
        "using_secret_fallback": True,
        "fallback_secret_default": secret == _DEFAULT_SECRET,
    }


def _fernet():
    raw = (os.getenv("APP_ENCRYPTION_KEY") or "").strip()
    if raw:
        try:
            return Fernet(raw.encode())
        except Exception as exc:
            raise RuntimeError("APP_ENCRYPTION_KEY inválida") from exc

    seed = os.getenv("SECRET_KEY", _DEFAULT_SECRET).encode()
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
