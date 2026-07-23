"""
Production settings for Render.

Use with DJANGO_SETTINGS_MODULE=core.settings.production.
This module keeps the shared settings package intact and only tightens the
pieces that must be explicit in production.
"""
from urllib.parse import parse_qs, unquote, urlparse

from decouple import config
from django.core.exceptions import ImproperlyConfigured

from . import *  # noqa: F401, F403
from ._helpers import _csv, _str


def _required_str(key: str) -> str:
    value = _str(key).strip()
    if not value:
        raise ImproperlyConfigured(f'{key} must be configured in production.')
    return value


def _required_csv(key: str) -> list[str]:
    values = _csv(key, '')
    if not values:
        raise ImproperlyConfigured(f'{key} must be configured in production.')
    return values


def _database_from_url(database_url: str) -> dict[str, object]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {'postgres', 'postgresql'}:
        raise ImproperlyConfigured('DATABASE_URL must use postgres:// or postgresql://.')
    if not parsed.hostname or not parsed.path.lstrip('/'):
        raise ImproperlyConfigured('DATABASE_URL must include host and database name.')

    query_params = parse_qs(parsed.query)
    options: dict[str, str] = {'options': '-c client_encoding=UTF8'}
    if 'sslmode' in query_params and query_params['sslmode']:
        options['sslmode'] = query_params['sslmode'][-1]

    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(parsed.path.lstrip('/')),
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': parsed.hostname,
        'PORT': str(parsed.port or 5432),
        'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
        'OPTIONS': options,
    }


DEBUG = False
SECRET_KEY = _required_str('DJANGO_SECRET_KEY')

DATABASES = {
    'default': _database_from_url(_required_str('DATABASE_URL')),
}

ALLOWED_HOSTS = _required_csv('DJANGO_ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = _required_csv('CSRF_TRUSTED_ORIGINS')
CORS_ALLOWED_ORIGINS = _required_csv('CORS_ALLOWED_ORIGINS')
CORS_ALLOWED_ORIGIN_REGEXES = _csv('CORS_ALLOWED_ORIGIN_REGEXES', '')
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=False, cast=bool)

EMAIL_BACKEND = _str(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
DEFAULT_FROM_EMAIL = _required_str('DEFAULT_FROM_EMAIL')
EMAIL_HOST = _required_str('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = _required_str('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = _required_str('EMAIL_HOST_PASSWORD')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

SERVE_MEDIA_FILES = config('SERVE_MEDIA_FILES', default=False, cast=bool)
ALLOW_OTP_FALLBACK = False
OTP_FALLBACK_CODE = ''