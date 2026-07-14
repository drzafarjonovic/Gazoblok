"""Autentifikatsiya yordamchilari: parol hash (pbkdf2) va JWT token.

Qo'shimcha og'ir kutubxonalarsiz — parol hash uchun standart `hashlib`,
token uchun yengil `PyJWT` ishlatiladi.
"""
import os
import hmac
import time
import hashlib
import secrets
from pathlib import Path

import jwt  # PyJWT

_SECRET_FILE = Path(__file__).with_name(".secret")


def _get_secret() -> str:
    """JWT imzo kaliti. .env dagi API_SECRET, yoki avtomatik yaratilib faylga saqlanadi."""
    s = os.getenv("API_SECRET")
    if s:
        return s
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text().strip()
    s = secrets.token_hex(32)
    try:
        _SECRET_FILE.write_text(s)
    except Exception:
        pass
    return s


SECRET = _get_secret()
ALGO = "HS256"
TOKEN_TTL = 60 * 60 * 24 * 30  # 30 kun


def hash_password(parol: str) -> str:
    salt = secrets.token_bytes(16)
    iters = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", parol.encode(), salt, iters)
    return f"pbkdf2${iters}${salt.hex()}${dk.hex()}"


def verify_password(parol: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", parol.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def create_token(user_id: int, rol: str) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "rol": rol, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=[ALGO])
