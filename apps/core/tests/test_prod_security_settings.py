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
                "SECURE_CONTENT_TYPE_NOSNIFF": True,
                "X_FRAME_OPTIONS": "DENY",
                "SECURE_REFERRER_POLICY": "same-origin",
                "CSRF_TRUSTED_ORIGINS": ["https://example.com"],
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
                "SECURE_CONTENT_TYPE_NOSNIFF": False,
                "X_FRAME_OPTIONS": None,
                "SECURE_REFERRER_POLICY": None,
                "CSRF_TRUSTED_ORIGINS": [],
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
            "SECURE_CONTENT_TYPE_NOSNIFF": True,
            "X_FRAME_OPTIONS": "DENY",
            "SECURE_REFERRER_POLICY": "same-origin",
            "CSRF_TRUSTED_ORIGINS": ["https://example.com"],
        }
    )


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        ({"SECURE_CONTENT_TYPE_NOSNIFF": False}, "SECURE_CONTENT_TYPE_NOSNIFF"),
        ({"X_FRAME_OPTIONS": ""}, "X_FRAME_OPTIONS"),
        ({"SECURE_REFERRER_POLICY": ""}, "SECURE_REFERRER_POLICY"),
        ({"CSRF_TRUSTED_ORIGINS": []}, "CSRF_TRUSTED_ORIGINS"),
    ],
)
def test_validate_production_security_rejects_missing_additional_hardening(overrides, expected_message):
    settings_dict = {
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
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "X_FRAME_OPTIONS": "DENY",
        "SECURE_REFERRER_POLICY": "same-origin",
        "CSRF_TRUSTED_ORIGINS": ["https://example.com"],
    }
    settings_dict.update(overrides)

    with pytest.raises(ImproperlyConfigured, match=expected_message):
        validate_production_security(settings_dict)
