"""
Symmetric encryption for secrets at rest (the WLC password stored in MongoDB).

The Fernet key is derived from SECRET_ENCRYPTION_KEY if set, otherwise from
JWT_SECRET (which production already requires to be strong). Encrypted values
carry an "enc:v1:" prefix so decrypt_secret() can transparently pass through
legacy cleartext values — existing rows keep working and get encrypted on their
next save.

Caveat: rotating the underlying key makes previously-stored secrets
undecryptable; the admin would simply re-enter the WLC password once.
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from config import JWT_SECRET
import os

log = logging.getLogger("Crypto")

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    material = os.getenv("SECRET_ENCRYPTION_KEY") or JWT_SECRET
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    """Return an 'enc:v1:'-prefixed ciphertext. Empty input stays empty."""
    if not plain:
        return ""
    token = _fernet().encrypt(plain.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt_secret(stored: str) -> str:
    """Decrypt a stored secret. Values without the prefix are treated as legacy
    cleartext and returned unchanged (backward-compatible migration)."""
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored  # legacy cleartext
    try:
        return _fernet().decrypt(stored[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        log.error(f"Failed to decrypt stored secret (key changed?): {e}")
        return ""