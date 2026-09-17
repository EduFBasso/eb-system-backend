import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings as django_settings
from django.core import signing
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.authentication.models import ProfessionalSettings
from apps.authentication.serializers.serializers import ProfessionalSettingsSerializer
from apps.notifications.models import TelegramProfessionalLink
from apps.notifications.services.telegram_client import TelegramBotClient, TelegramDeliveryError
from utils.permissions import get_active_tenant


TELEGRAM_LINK_TOKEN_TTL_SECONDS = 15 * 60


def _to_base36(value: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    digits = []
    number = int(value)
    while number:
        number, remainder = divmod(number, 36)
        digits.append(chars[remainder])
    return "".join(reversed(digits))


def _from_base36(value: str) -> int:
    return int(value, 36)


def _token_key() -> bytes:
    secret = signing.Signer(salt="telegram-link").signature("seed")
    return secret.encode("utf-8")


def _token_signature(payload: str) -> str:
    digest = hmac.new(
        _token_key(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return digest[:16]


def _build_telegram_link_token(professional_id: int) -> str:
    professional_id_base36 = _to_base36(professional_id)
    timestamp_base36 = _to_base36(int(timezone.now().timestamp()))
    nonce = secrets.token_urlsafe(4).replace("-", "").replace("_", "")[:6].lower()
    payload = f"{professional_id_base36}-{timestamp_base36}-{nonce}"
    signature = _token_signature(payload)
    return f"{payload}-{signature}"


def _parse_telegram_link_token(token: str) -> dict | None:
    try:
        professional_id_base36, timestamp_base36, nonce, signature = token.split("-", 3)
    except ValueError:
        return None

    payload = f"{professional_id_base36}-{timestamp_base36}-{nonce}"
    expected_signature = _token_signature(payload)
    if not hmac.compare_digest(expected_signature, signature):
        return None

    try:
        professional_id = _from_base36(professional_id_base36)
        timestamp = _from_base36(timestamp_base36)
    except Exception:
        return None

    return {"pid": professional_id, "ts": timestamp, "nonce": nonce}


class ClinicProfessionalActionsMixin:
    """Acoes de settings e integracao Telegram exclusivas do Clinic."""

    @action(detail=False, methods=["get", "patch"], url_path="settings")
    def professional_settings(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        obj, _ = ProfessionalSettings.objects.get_or_create(professional_id=user.id)

        def with_runtime_flags(payload: dict):
            data = dict(payload)
            data["reminders_globally_enabled"] = bool(
                django_settings.APPOINTMENT_REMINDERS_ENABLED
            )
            link = TelegramProfessionalLink.objects.filter(
                professional_id=user.id
            ).first()
            data["telegram_linked"] = bool(link)
            data["telegram_link_active"] = bool(link.is_active) if link else False
            data["telegram_username"] = link.telegram_username if link else ""
            data["telegram_last_error"] = link.last_error if link else ""
            return data

        if request.method.lower() == "patch":
            serializer = ProfessionalSettingsSerializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            try:
                serializer.save()
            except Exception as exc:
                return Response({"detail": str(exc)}, status=400)
            return Response(with_runtime_flags(serializer.data))
        return Response(with_runtime_flags(ProfessionalSettingsSerializer(obj).data))

    @action(detail=False, methods=["get"], url_path="telegram/link-start")
    def telegram_link_start(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)

        client = TelegramBotClient()
        if not client.is_configured:
            return Response(
                {
                    "detail": "Bot do Telegram não configurado no servidor.",
                    "bot_configured": False,
                },
                status=503,
            )

        try:
            me = client.get_me()
        except TelegramDeliveryError as exc:
            return Response(
                {"detail": str(exc), "bot_configured": False},
                status=502,
            )

        bot_username = str(me.get("username") or "").strip()
        if not bot_username:
            return Response(
                {
                    "detail": "Não foi possível identificar username do bot.",
                    "bot_configured": False,
                },
                status=502,
            )

        token = _build_telegram_link_token(user.id)
        link_url = f"https://t.me/{bot_username}?start={token}"
        expires_at = timezone.now() + timedelta(seconds=TELEGRAM_LINK_TOKEN_TTL_SECONDS)

        return Response(
            {
                "bot_configured": True,
                "bot_username": bot_username,
                "start_token": token,
                "link_url": link_url,
                "expires_at": expires_at.isoformat(),
            }
        )

    @action(detail=False, methods=["post"], url_path="telegram/link-verify")
    def telegram_link_verify(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)

        token = str(request.data.get("start_token") or "").strip()
        if not token:
            return Response({"detail": "start_token é obrigatório."}, status=400)

        payload = _parse_telegram_link_token(token)
        if not payload:
            return Response({"detail": "Token inválido."}, status=400)

        pid = payload.get("pid")
        timestamp = payload.get("ts")
        if not isinstance(pid, int) or pid != user.id:
            return Response({"detail": "Token não pertence ao usuário logado."}, status=403)
        if not isinstance(timestamp, int):
            return Response({"detail": "Token inválido."}, status=400)

        now_timestamp = int(timezone.now().timestamp())
        if now_timestamp - timestamp > TELEGRAM_LINK_TOKEN_TTL_SECONDS:
            return Response({"detail": "Token expirado. Gere um novo vínculo."}, status=400)

        client = TelegramBotClient()
        if not client.is_configured:
            return Response(
                {"detail": "Bot do Telegram não configurado no servidor.", "linked": False},
                status=503,
            )

        try:
            updates = client.get_updates(limit=100, timeout=0, allowed_updates=["message"])
        except TelegramDeliveryError as exc:
            return Response({"detail": str(exc), "linked": False}, status=502)

        matched_chat_id = None
        matched_username = ""
        expected_start = f"/start {token}"

        for update in reversed(updates):
            message = update.get("message") if isinstance(update, dict) else None
            if not isinstance(message, dict) or str(message.get("text") or "").strip() != expected_start:
                continue
            chat = message.get("chat")
            if not isinstance(chat, dict) or chat.get("id") is None:
                continue
            matched_chat_id = str(chat["id"])
            matched_username = str(chat.get("username") or "").strip()
            break

        if not matched_chat_id:
            return Response(
                {
                    "linked": False,
                    "detail": "Não encontramos o /start deste vínculo ainda. Abra o link no Telegram e toque em Iniciar, depois tente novamente.",
                },
                status=409,
            )

        tenant = get_active_tenant(user)
        if not tenant:
            membership = user.tenant_memberships.filter(is_active=True).first()
            if membership:
                tenant = membership.tenant

        defaults = {
            "chat_id": matched_chat_id,
            "telegram_username": matched_username,
            "is_active": True,
            "last_error": "",
        }
        if tenant:
            defaults["tenant"] = tenant

        TelegramProfessionalLink.objects.update_or_create(
            professional_id=user.id,
            defaults=defaults,
        )

        phone_display = str(user.phone) if getattr(user, "phone", None) else ""
        welcome_lines = [
            "✅ Conexão estabelecida com sucesso!",
            "",
            f"👤 Usuário: {user.get_full_name() or user.first_name}",
        ]
        if phone_display:
            welcome_lines.append(f"📱 Telefone integrado: {phone_display}")
        welcome_lines.extend([
            "",
            "Este canal está ativo para recebimento de alertas e tokens de segurança do sistema.",
        ])
        try:
            client.send_message(chat_id=matched_chat_id, text="\n".join(welcome_lines))
        except Exception:
            pass

        return Response(
            {
                "linked": True,
                "chat_id": matched_chat_id,
                "telegram_username": matched_username,
            }
        )

    @action(detail=False, methods=["post"], url_path="telegram/test-send")
    def telegram_test_send(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)

        try:
            link = TelegramProfessionalLink.objects.get(
                professional_id=user.id, is_active=True
            )
        except TelegramProfessionalLink.DoesNotExist:
            return Response(
                {"detail": "Telegram não conectado. Faça o vínculo primeiro."},
                status=400,
            )

        client = TelegramBotClient()
        if not client.is_configured:
            return Response(
                {"detail": "Bot do Telegram não configurado no servidor."},
                status=503,
            )

        try:
            result = client.send_message(
                chat_id=link.chat_id,
                text="✅ Teste de notificação — sistema Clínica conectado com sucesso!",
            )
        except TelegramDeliveryError as exc:
            return Response({"detail": str(exc)}, status=502)

        return Response({"ok": True, "message_id": result.message_id})


__all__ = [
    "ClinicProfessionalActionsMixin",
    "TELEGRAM_LINK_TOKEN_TTL_SECONDS",
    "_build_telegram_link_token",
    "_parse_telegram_link_token",
]
