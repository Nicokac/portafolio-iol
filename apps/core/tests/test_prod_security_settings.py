import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.security import (
    secret_key_is_strong,
    validate_production_security,
)


def test_secret_key_strength_accepts_long_random_keys():
    assert secret_key_is_strong("a9F!kLm2Qx7#uP0rTz5@vBn8$yH1*cDe4&Gh6Jk9LmNoPqRs7Tu8")


def test_secret_key_strength_rejects_default_style_keys():
    assert not secret_key_is_strong("django-insecure-test-key")


def test_validate_production_security_rejects_debug_true():
    with pytest.raises(ImproperlyConfigured):
        validate_production_security(
            {
                "DEBUG": True,
                "SECRET_KEY": "a9F!kLm2Qx7#uP0rTz5@vBn8$yH1*cDe4&Gh6Jk9LmNoPqRs7Tu8",
                "IOL_USERNAME": "user",
                "IOL_PASSWORD": "pass",
                "ALLOWED_HOSTS": ["example.com"],
                "SECURE_SSL_REDIRECT": True,
                "SESSION_COOKIE_SECURE": True,
                "CSRF_COOKIE_SECURE": True,
                "SESSION_COOKIE_HTTPONLY": True,
                "SECURE_HSTS_SECONDS": 31536000,
                "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
            }
        )


def test_validate_production_security_rejects_missing_critical_flags():
    with pytest.raises(ImproperlyConfigured):
        validate_production_security(
            {
                "DEBUG": False,
                "SECRET_KEY": "django-insecure-test-key",
                "IOL_USERNAME": "user",
                "IOL_PASSWORD": "pass",
                "ALLOWED_HOSTS": [],
                "SECURE_SSL_REDIRECT": False,
                "SESSION_COOKIE_SECURE": False,
                "CSRF_COOKIE_SECURE": False,
                "SESSION_COOKIE_HTTPONLY": False,
                "SECURE_HSTS_SECONDS": 0,
                "SECURE_PROXY_SSL_HEADER": None,
            }
        )


def test_validate_production_security_accepts_hardened_configuration():
    validate_production_security(
            {
                "DEBUG": False,
                "SECRET_KEY": "a9F!kLm2Qx7#uP0rTz5@vBn8$yH1*cDe4&Gh6Jk9LmNoPqRs7Tu8",
            "IOL_USERNAME": "user",
            "IOL_PASSWORD": "pass",
            "ALLOWED_HOSTS": ["example.com"],
            "SECURE_SSL_REDIRECT": True,
            "SESSION_COOKIE_SECURE": True,
            "CSRF_COOKIE_SECURE": True,
            "SESSION_COOKIE_HTTPONLY": True,
            "SECURE_HSTS_SECONDS": 31536000,
            "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        }
    )
