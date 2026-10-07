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
    from apps.authentication.ecosystems import get_ecosystem

    try:
        spec = get_ecosystem(ecosystem)
    except ValueError:
        raise ValueError(f"Ecossistema Telegram não suportado: {ecosystem}")

    return TelegramBotConfig(
        token=(getattr(settings, spec.telegram_token_setting) or "").strip(),
        api_base=getattr(settings, spec.telegram_api_base_setting),
        timeout=getattr(settings, spec.telegram_timeout_setting),
    )
