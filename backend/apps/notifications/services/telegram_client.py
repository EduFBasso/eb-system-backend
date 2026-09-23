from __future__ import annotations

from dataclasses import dataclass

import requests

from django.conf import settings

from .. import models as notifications_models


class TelegramDeliveryError(Exception):
    pass


@dataclass
class TelegramSendResult:
    ok: bool
    message_id: str
    raw: dict


class TelegramBotClient:
    def __init__(
        self,
        token: str | None = None,
        api_base: str | None = None,
        timeout: int | None = None,
        ecosystem: str = "clinic",
    ):
        self.ecosystem = ecosystem
        if token is None:
            token = (
                settings.BAKERY_TELEGRAM_BOT_TOKEN
                if ecosystem == "bakery"
                else settings.CLINIC_TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN
            )
        self.token = token
        self.api_base = (
            api_base
            if api_base is not None
            else (
                settings.BAKERY_TELEGRAM_BOT_API_BASE
                if ecosystem == "bakery"
                else settings.CLINIC_TELEGRAM_BOT_API_BASE
            )
        ).rstrip("/")
        self.timeout = (
            timeout
            if timeout is not None
            else (
                settings.BAKERY_TELEGRAM_BOT_TIMEOUT_SECONDS
                if ecosystem == "bakery"
                else settings.CLINIC_TELEGRAM_BOT_TIMEOUT_SECONDS
            )
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
    ) -> TelegramSendResult:
        if not self.is_configured:
            raise TelegramDeliveryError("Token do bot Telegram não configurado.")

        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(
                f"{self.api_base}/bot{self.token}/sendMessage",
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TelegramDeliveryError(
                f"Erro HTTP ao enviar para Telegram: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramDeliveryError(
                f"Resposta inválida do Telegram (status {response.status_code})."
            ) from exc

        if response.status_code >= 400 or not data.get("ok"):
            description = data.get("description") or response.text
            raise TelegramDeliveryError(
                f"Telegram recusou a mensagem: {description}"
            )

        result = data.get("result") or {}
        return TelegramSendResult(
            ok=True,
            message_id=str(result.get("message_id", "")),
            raw=data,
        )

    def get_me(self) -> dict:
        if not self.is_configured:
            raise TelegramDeliveryError("Token do bot Telegram não configurado.")

        try:
            response = requests.get(
                f"{self.api_base}/bot{self.token}/getMe",
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TelegramDeliveryError(
                f"Erro HTTP ao consultar Telegram (getMe): {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramDeliveryError(
                f"Resposta inválida do Telegram (status {response.status_code})."
            ) from exc

        if response.status_code >= 400 or not data.get("ok"):
            description = data.get("description") or response.text
            raise TelegramDeliveryError(
                f"Telegram recusou getMe: {description}"
            )

        return data.get("result") or {}

    def get_updates(
        self,
        *,
        limit: int = 100,
        timeout: int = 0,
        allowed_updates: list[str] | None = None,
    ) -> list[dict]:
        if not self.is_configured:
            raise TelegramDeliveryError("Token do bot Telegram não configurado.")

        payload: dict[str, object] = {
            "limit": max(1, min(int(limit), 100)),
            "timeout": max(0, int(timeout)),
        }
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates

        try:
            response = requests.get(
                f"{self.api_base}/bot{self.token}/getUpdates",
                params=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TelegramDeliveryError(
                f"Erro HTTP ao consultar Telegram (getUpdates): {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramDeliveryError(
                f"Resposta inválida do Telegram (status {response.status_code})."
            ) from exc

        if response.status_code >= 400 or not data.get("ok"):
            description = data.get("description") or response.text
            raise TelegramDeliveryError(
                f"Telegram recusou getUpdates: {description}"
            )

        result = data.get("result")
        if isinstance(result, list):
            return result
        return []


def masked_token_fingerprint(token: str) -> str:
    tail = (token or '').strip()[-4:]
    return f"***{tail}" if tail else "***"


def _default_bot_token(ecosystem: str) -> tuple[str, str]:
    ecosystem_token = (
        settings.BAKERY_TELEGRAM_BOT_TOKEN
        if ecosystem == "bakery"
        else settings.CLINIC_TELEGRAM_BOT_TOKEN
    )
    if ecosystem_token:
        return ecosystem_token.strip(), ecosystem
    return (settings.TELEGRAM_BOT_TOKEN or '').strip(), 'global'


def resolve_bot_token(link: "notifications_models.TelegramProfessionalLink") -> tuple[str, str]:
    """Resolve o token privado ou o token padrão do ecossistema do vínculo."""
    private_token = (link.bot_token or '').strip()
    if private_token:
        return private_token, 'professional'
    ecosystem = link.tenant.ecosystem
    return _default_bot_token(ecosystem)


def send_via_link(
    link: "notifications_models.TelegramProfessionalLink",
    *,
    text: str,
    reply_markup: dict | None = None,
) -> TelegramSendResult:
    """Resolves the right bot token for a link (own bot or global fallback) and sends a message."""
    token, _origin = resolve_bot_token(link)
    client = TelegramBotClient(token=token, ecosystem=link.tenant.ecosystem)
    return client.send_message(chat_id=link.chat_id, text=text, reply_markup=reply_markup)
