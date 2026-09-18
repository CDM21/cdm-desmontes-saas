import base64
import hashlib
import os
from cryptography.fernet import Fernet, InvalidToken

_DEFAULT_SECRET = "CHANGE_THIS_SECRET_IN_PRODUCTION"


def _legacy_fernet():
    seed = os.getenv("SECRET_KEY", _DEFAULT_SECRET).encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(key)


def _explicit_fernet():
    raw = (os.getenv("APP_ENCRYPTION_KEY") or "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode())
    except Exception as exc:
        raise RuntimeError("APP_ENCRYPTION_KEY inválida") from exc


def encryption_key_status():
    raw = (os.getenv("APP_ENCRYPTION_KEY") or "").strip()
    if raw:
        try:
            Fernet(raw.encode())
            valid = True
        except Exception:
            valid = False
        return {
            "configured": True,
            "valid": valid,
            "using_secret_fallback": False,
            "fallback_secret_default": False,
            "legacy_decryption_supported": True,
        }

    secret = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
    return {
        "configured": False,
        "valid": False,
        "using_secret_fallback": True,
        "fallback_secret_default": secret == _DEFAULT_SECRET,
        "legacy_decryption_supported": True,
    }


def encrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    cipher = _explicit_fernet() or _legacy_fernet()
    return cipher.encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""

    explicit = _explicit_fernet()
    if explicit is not None:
        try:
            return explicit.decrypt(value.encode()).decode()
        except InvalidToken:
            # Compatibilidade segura durante a rotação:
            # tenta apenas a chave antiga derivada da SECRET_KEY.
            try:
                return _legacy_fernet().decrypt(value.encode()).decode()
            except Exception:
                return ""
        except Exception:
            return ""

    try:
        return _legacy_fernet().decrypt(value.encode()).decode()
    except Exception:
        return ""


def rotate_secret(value: str | None):
    """
    Recriptografa um segredo legado com APP_ENCRYPTION_KEY.
    Retorna (novo_valor, alterado). Nunca expõe o texto puro.
    """
    if not value:
        return "", False

    explicit = _explicit_fernet()
    if explicit is None:
        return value, False

    try:
        explicit.decrypt(value.encode())
        return value, False
    except InvalidToken:
        pass

    try:
        plain = _legacy_fernet().decrypt(value.encode())
    except Exception:
        raise RuntimeError("Segredo existente não pôde ser descriptografado")

    return explicit.encrypt(plain).decode(), True
