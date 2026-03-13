import pytest

from apps.core.utils.token_crypto import decrypt_token, encrypt_token


def test_encrypt_token_roundtrip():
    ciphertext = encrypt_token("secret-token")
    assert ciphertext != "secret-token"
    assert decrypt_token(ciphertext) == "secret-token"


def test_encrypt_token_is_compatible_with_plaintext_legacy_values():
    assert decrypt_token("legacy-token") == "legacy-token"


def test_decrypt_token_rejects_tampering():
    ciphertext = encrypt_token("secret-token")
    tampered = ciphertext[:-1] + ("A" if ciphertext[-1] != "A" else "B")
    with pytest.raises(ValueError):
        decrypt_token(tampered)
