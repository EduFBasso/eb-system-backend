from __future__ import annotations

from dataclasses import dataclass

import requests

from django.conf import settings


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
    ):
        self.token = token if token is not None else settings.TELEGRAM_BOT_TOKEN
        self.api_base = (
            api_base if api_base is not None else settings.TELEGRAM_BOT_API_BASE
        ).rstrip("/")
        self.timeout = (
            timeout
            if timeout is not None
            else settings.TELEGRAM_BOT_TIMEOUT_SECONDS
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
            raise TelegramDeliveryError("TELEGRAM_BOT_TOKEN não configurado.")

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
            raise TelegramDeliveryError("TELEGRAM_BOT_TOKEN não configurado.")

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
            raise TelegramDeliveryError("TELEGRAM_BOT_TOKEN não configurado.")

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