from django.core.exceptions import ImproperlyConfigured


def secret_key_is_strong(secret_key: str) -> bool:
    if not secret_key:
        return False
    if secret_key.startswith("django-insecure-"):
        return False
    if len(secret_key) < 50:
        return False
    if len(set(secret_key)) < 5:
        return False
    return True


def validate_production_security(settings_dict: dict) -> None:
    required_truthy = [
        "SECRET_KEY",
        "IOL_USERNAME",
        "IOL_PASSWORD",
        "ALLOWED_HOSTS",
        "SECURE_SSL_REDIRECT",
        "SESSION_COOKIE_SECURE",
        "CSRF_COOKIE_SECURE",
        "SESSION_COOKIE_HTTPONLY",
        "SECURE_HSTS_SECONDS",
        "SECURE_PROXY_SSL_HEADER",
    ]

    missing = [key for key in required_truthy if not settings_dict.get(key)]
    if missing:
        raise ImproperlyConfigured(
            f"Missing or insecure production settings: {', '.join(missing)}"
        )

    if settings_dict.get("DEBUG"):
        raise ImproperlyConfigured("DEBUG must be False in production")

    if not secret_key_is_strong(str(settings_dict.get("SECRET_KEY", ""))):
        raise ImproperlyConfigured("SECRET_KEY is too weak for production")

    if settings_dict.get("SECURE_CONTENT_TYPE_NOSNIFF") is not True:
        raise ImproperlyConfigured("SECURE_CONTENT_TYPE_NOSNIFF must be True in production")

    if not settings_dict.get("X_FRAME_OPTIONS"):
        raise ImproperlyConfigured("X_FRAME_OPTIONS must be configured in production")

    if not settings_dict.get("SECURE_REFERRER_POLICY"):
        raise ImproperlyConfigured("SECURE_REFERRER_POLICY must be configured in production")

    if not settings_dict.get("CSRF_TRUSTED_ORIGINS"):
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS cannot be empty in production")
