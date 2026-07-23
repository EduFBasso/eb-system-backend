"""
Integrações externas: Telegram bot (usado pelo serviço de lembretes).
"""
from decouple import config

# === Integração Telegram ===

TELEGRAM_BOT_TOKEN: str = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_API_BASE: str = config(
    "TELEGRAM_BOT_API_BASE", default="https://api.telegram.org"
)
TELEGRAM_BOT_TIMEOUT_SECONDS: int = config(
    "TELEGRAM_BOT_TIMEOUT_SECONDS", default=10, cast=int
)
