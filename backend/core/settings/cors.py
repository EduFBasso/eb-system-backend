"""
CORS e hosts permitidos: ALLOWED_HOSTS, origens e cabeçalhos CORS.
Em modo LAN (DEV_ALLOW_LAN_HOSTS), expande automaticamente para redes privadas.
"""
from corsheaders.defaults import default_headers
from decouple import config

from ._helpers import DEV_ALLOW_LAN_HOSTS, _csv

# === Hosts Permitidos ===

ALLOWED_HOSTS: list[str] = _csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

if DEV_ALLOW_LAN_HOSTS:
    ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, '*', '.local']))

# === CORS ===

CORS_ALLOWED_ORIGINS: list[str] = _csv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

CORS_ALLOWED_ORIGIN_REGEXES: list[str] = _csv("CORS_ALLOWED_ORIGIN_REGEXES", "")

if DEV_ALLOW_LAN_HOSTS and not CORS_ALLOWED_ORIGIN_REGEXES:
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https?://10(?:\.\d{1,3}){3}(?::\d+)?$",
        r"^https?://192\.168(?:\.\d{1,3}){2}(?::\d+)?$",
        r"^https?://172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}(?::\d+)?$",
        r"^https?://[a-z0-9-]+\.local(?::\d+)?$",
    ]

CORS_ALLOW_ALL_ORIGINS: bool = config("CORS_ALLOW_ALL_ORIGINS", default=False, cast=bool)
CORS_ALLOW_CREDENTIALS: bool = config("CORS_ALLOW_CREDENTIALS", default=False, cast=bool)

CORS_ALLOW_HEADERS: list[str] = list(default_headers) + [
    'x-device-id',
    'x-device-info',
    'x-client-now',
]

CORS_PREFLIGHT_MAX_AGE: int = config("CORS_PREFLIGHT_MAX_AGE", default=600, cast=int)
