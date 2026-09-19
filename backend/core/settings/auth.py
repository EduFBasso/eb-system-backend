"""Autenticação e autorização: DRF, JWT e sessões de dispositivo."""
from datetime import timedelta

from decouple import config

from ._helpers import DEBUG

# === Django REST Framework ===

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.authentication.services.auth_device.JWTDeviceAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] if not DEBUG else [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# === JWT (SimpleJWT) ===

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# === Sessões de Dispositivo ===

MAX_ACTIVE_DEVICE_SESSIONS: int = config(
    "MAX_ACTIVE_DEVICE_SESSIONS", default=2, cast=int
)
