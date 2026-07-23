"""
Autenticação e autorização: DRF, JWT, OTP, sessões de dispositivo, TOTP e WebAuthn.
"""
from datetime import timedelta

from decouple import config

from ._helpers import DEBUG, _csv

# === Django REST Framework ===

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.register.auth_device.JWTDeviceAuthentication',
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

# === OTP e Sessões de Dispositivo ===

ALLOW_OTP_FALLBACK: bool = config("ALLOW_OTP_FALLBACK", default=False, cast=bool)
OTP_FALLBACK_CODE: str = config("OTP_FALLBACK_CODE", default="")

MAX_ACTIVE_DEVICE_SESSIONS: int = config(
    "MAX_ACTIVE_DEVICE_SESSIONS", default=2, cast=int
)

# === TOTP ===

TOTP_ISSUER: str = config("TOTP_ISSUER", default="ClinicSystem")
# valid_window=4 → accepts codes ±120s from server time.
# Needed on mobile (iOS): user opens authenticator app, memorises code,
# switches back to browser and types — easily 20-40s of elapsed time.
# With a code near the end of its 30s window this can exceed ±60s (window=2).
# 4 windows (±120s) is the safe mobile standard; still rejects replays outside that range.
TOTP_VALID_WINDOW: int = config("TOTP_VALID_WINDOW", default=4, cast=int)

# === WebAuthn / Passkeys ===

# rpId: domínio sem esquema/porta. localhost para dev; domínio real em produção.
WEBAUTHN_RP_ID: str = config("WEBAUTHN_RP_ID", default="localhost")
WEBAUTHN_RP_NAME: str = config("WEBAUTHN_RP_NAME", default="ClinicSystem")
# Origens aceitas separadas por vírgula (incluir http em dev, https em produção)
WEBAUTHN_ORIGINS: list[str] = _csv("WEBAUTHN_ORIGINS", "http://localhost:5173")
