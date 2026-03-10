from .base import *
from decouple import config

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# Production database
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': config('DB_NAME'),
    'USER': config('DB_USER'),
    'PASSWORD': config('DB_PASSWORD'),
    'HOST': config('DB_HOST', default='localhost'),
    'PORT': config('DB_PORT', default='5432'),
}

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_REFERRER_POLICY = 'same-origin'
CSRF_TRUSTED_ORIGINS = [origin for origin in config('CSRF_TRUSTED_ORIGINS', default='').split(',') if origin]

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
    }
}

# Sentry (optional)
if os.getenv('SENTRY_DSN'):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# Validate critical settings
required_settings = ['SECRET_KEY', 'IOL_USERNAME', 'IOL_PASSWORD']
for setting in required_settings:
    if not globals().get(setting):
        raise ValueError(f"Required setting {setting} is not set in production.")
