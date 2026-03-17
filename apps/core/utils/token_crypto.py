import base64
import hashlib
import hmac
import os

from django.conf import settings


TOKEN_PREFIX = "enc::"
NONCE_SIZE = 16
TAG_SIZE = 32
BLOCK_SIZE = 32


def _get_secret() -> bytes:
    return hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def _keystream(secret: bytes, nonce: bytes, length: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        block = hmac.new(
            secret,
            nonce + counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()
        output.extend(block)
        counter += 1
    return bytes(output[:length])


def encrypt_token(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    if is_encrypted_token(value):
        return value

    plaintext = value.encode("utf-8")
    secret = _get_secret()
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = _xor_bytes(plaintext, _keystream(secret, nonce, len(plaintext)))
    tag = hmac.new(secret, nonce + ciphertext, hashlib.sha256).digest()
    payload = base64.urlsafe_b64encode(nonce + ciphertext + tag).decode("ascii")
    return f"{TOKEN_PREFIX}{payload}"


def is_encrypted_token(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(TOKEN_PREFIX)


def decrypt_token(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    if not is_encrypted_token(value):
        return value

    payload = base64.urlsafe_b64decode(value[len(TOKEN_PREFIX):].encode("ascii"))
    nonce = payload[:NONCE_SIZE]
    tag = payload[-TAG_SIZE:]
    ciphertext = payload[NONCE_SIZE:-TAG_SIZE]
    secret = _get_secret()
    expected_tag = hmac.new(secret, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Encrypted token integrity check failed")

    plaintext = _xor_bytes(ciphertext, _keystream(secret, nonce, len(ciphertext)))
    return plaintext.decode("utf-8")
