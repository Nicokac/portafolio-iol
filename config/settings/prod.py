from .base import *

DEBUG = False

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Production database
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.getenv('DB_NAME'),
    'USER': os.getenv('DB_USER'),
    'PASSWORD': os.getenv('DB_PASSWORD'),
    'HOST': os.getenv('DB_HOST', 'localhost'),
    'PORT': os.getenv('DB_PORT', '5432'),
}

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

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
        traces_sample_rate=1.0,
        send_default_pii=True,
    )

# Validate critical settings
required_settings = ['SECRET_KEY', 'IOL_USERNAME', 'IOL_PASSWORD']
for setting in required_settings:
    if not globals().get(setting):
        raise ValueError(f"Required setting {setting} is not set in production.")