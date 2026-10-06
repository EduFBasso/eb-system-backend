from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.conf import settings


TelegramEcosystem = Literal["clinic", "bakery"]


@dataclass(frozen=True)
class TelegramBotConfig:
    token: str
    api_base: str
    timeout: int


def get_telegram_bot_config(ecosystem: str) -> TelegramBotConfig:
    """Return the explicit Telegram configuration for one ecosystem."""
    if ecosystem == "clinic":
        return TelegramBotConfig(
            token=(settings.CLINIC_TELEGRAM_BOT_TOKEN or "").strip(),
            api_base=settings.CLINIC_TELEGRAM_BOT_API_BASE,
            timeout=settings.CLINIC_TELEGRAM_BOT_TIMEOUT_SECONDS,
        )
    if ecosystem == "bakery":
        return TelegramBotConfig(
            token=(settings.BAKERY_TELEGRAM_BOT_TOKEN or "").strip(),
            api_base=settings.BAKERY_TELEGRAM_BOT_API_BASE,
            timeout=settings.BAKERY_TELEGRAM_BOT_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Ecossistema Telegram não suportado: {ecosystem}")
