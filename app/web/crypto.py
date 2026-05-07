"""At-rest obfuscation for OAuth tokens.

Wraps :class:`itsdangerous.URLSafeSerializer` keyed off ``JWT_SECRET``. This
is *not* real KMS-grade encryption — it's a signed payload — but it's enough
to keep OAuth tokens out of plain-text DB dumps. For a production deployment
you'd swap this for a real envelope-encryption layer (e.g. AWS KMS, GCP KMS).
"""
from typing import Optional

from itsdangerous import BadSignature, URLSafeSerializer

from app.core.config import settings


_SALT = "wa.integration.token.v1"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.JWT_SECRET, salt=_SALT)


def encrypt_token(plaintext: Optional[str]) -> Optional[str]:
    if not plaintext:
        return None
    return _serializer().dumps(plaintext)


def decrypt_token(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return None
    try:
        return _serializer().loads(ciphertext)
    except BadSignature:
        return None
