"""Configuração das integrações externas por ecossistema."""
from decouple import config

CLINIC_TELEGRAM_BOT_TOKEN: str = config(
    "CLINIC_TELEGRAM_BOT_TOKEN", default=""
)
CLINIC_TELEGRAM_BOT_API_BASE: str = config(
    "CLINIC_TELEGRAM_BOT_API_BASE", default="https://api.telegram.org"
)
CLINIC_TELEGRAM_BOT_TIMEOUT_SECONDS: int = config(
    "CLINIC_TELEGRAM_BOT_TIMEOUT_SECONDS", default=10, cast=int
)

BAKERY_TELEGRAM_BOT_TOKEN: str = config("BAKERY_TELEGRAM_BOT_TOKEN", default="")
BAKERY_TELEGRAM_BOT_API_BASE: str = config(
    "BAKERY_TELEGRAM_BOT_API_BASE", default="https://api.telegram.org"
)
BAKERY_TELEGRAM_BOT_TIMEOUT_SECONDS: int = config(
    "BAKERY_TELEGRAM_BOT_TIMEOUT_SECONDS", default=10, cast=int
)

TELEGRAM_BOT_TOKEN: str = config(
    "TELEGRAM_BOT_TOKEN", default=CLINIC_TELEGRAM_BOT_TOKEN
)
TELEGRAM_BOT_API_BASE: str = CLINIC_TELEGRAM_BOT_API_BASE
TELEGRAM_BOT_TIMEOUT_SECONDS: int = CLINIC_TELEGRAM_BOT_TIMEOUT_SECONDS
