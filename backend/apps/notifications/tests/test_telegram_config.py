import pytest

from apps.notifications.services.telegram_client import TelegramBotClient
from apps.notifications.services.telegram_config import get_telegram_bot_config


def test_clinic_client_uses_clinic_bot_settings(settings):
    settings.CLINIC_TELEGRAM_BOT_TOKEN = "clinic-token"
    settings.CLINIC_TELEGRAM_BOT_API_BASE = "https://clinic.example"
    settings.CLINIC_TELEGRAM_BOT_TIMEOUT_SECONDS = 7

    config = get_telegram_bot_config("clinic")
    client = TelegramBotClient(ecosystem="clinic")

    assert config.token == "clinic-token"
    assert config.api_base == "https://clinic.example"
    assert config.timeout == 7
    assert client.token == "clinic-token"
    assert client.api_base == "https://clinic.example"
    assert client.timeout == 7


def test_bakery_client_uses_bakery_bot_settings(settings):
    settings.BAKERY_TELEGRAM_BOT_TOKEN = "bakery-token"
    settings.BAKERY_TELEGRAM_BOT_API_BASE = "https://bakery.example"
    settings.BAKERY_TELEGRAM_BOT_TIMEOUT_SECONDS = 8

    config = get_telegram_bot_config("bakery")
    client = TelegramBotClient(ecosystem="bakery")

    assert config.token == "bakery-token"
    assert config.api_base == "https://bakery.example"
    assert config.timeout == 8
    assert client.token == "bakery-token"
    assert client.api_base == "https://bakery.example"
    assert client.timeout == 8


def test_unknown_telegram_ecosystem_is_rejected():
    with pytest.raises(ValueError, match="Ecossistema Telegram não suportado"):
        get_telegram_bot_config("unknown")


def test_clinic_client_does_not_fallback_to_legacy_token(settings):
    settings.CLINIC_TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_BOT_TOKEN = "legacy-token"

    client = TelegramBotClient(ecosystem="clinic")

    assert client.token == ""
    assert client.is_configured is False
