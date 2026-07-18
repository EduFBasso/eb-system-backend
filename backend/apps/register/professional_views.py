# backend\apps\register\views_professionals.py
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from .models import Professional, ProfessionalSettings
from .serializers import (
    ProfessionalSerializer,
    ProfessionalBasicSerializer,
    ProfessionalSettingsSerializer,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings as django_settings
from django.core import signing
from django.utils import timezone
from datetime import timedelta
import secrets
import hashlib
import hmac
from apps.reminders.models import TelegramProfessionalLink
from apps.reminders.services.telegram import TelegramBotClient, TelegramDeliveryError


TELEGRAM_LINK_TOKEN_TTL_SECONDS = 15 * 60


SELF_SERVICE_ACTIONS = {
    "me",
    "professional_settings",
    "telegram_link_start",
    "telegram_link_verify",
    "telegram_test_send",
}


class CanManageProfessionalDirectory(BasePermission):
    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(view, "action", None) in SELF_SERVICE_ACTIONS:
            return True
        return bool(
            getattr(request.user, "is_superuser", False)
            or getattr(request.user, "can_manage_professionals", False)
        )


def _to_base36(value: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    digits = []
    n = int(value)
    while n:
        n, rem = divmod(n, 36)
        digits.append(chars[rem])
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
    pid = _to_base36(professional_id)
    ts = _to_base36(int(timezone.now().timestamp()))
    nonce = secrets.token_urlsafe(4).replace("-", "").replace("_", "")[:6].lower()
    payload = f"{pid}-{ts}-{nonce}"
    sig = _token_signature(payload)
    return f"{payload}-{sig}"


def _parse_telegram_link_token(token: str) -> dict | None:
    try:
        pid36, ts36, nonce, sig = token.split("-", 3)
    except ValueError:
        return None

    payload = f"{pid36}-{ts36}-{nonce}"
    expected_sig = _token_signature(payload)
    if not hmac.compare_digest(expected_sig, sig):
        return None

    try:
        pid = _from_base36(pid36)
        ts = _from_base36(ts36)
    except Exception:
        return None

    return {"pid": pid, "ts": ts, "nonce": nonce}


class ProfessionalViewSet(ModelViewSet):
    queryset = Professional.objects.all()
    serializer_class = ProfessionalSerializer
    permission_classes = [IsAuthenticated, CanManageProfessionalDirectory]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superuser", False) or getattr(user, "can_manage_professionals", False):
            return Professional.objects.all()
        return Professional.objects.none()

    def perform_destroy(self, instance: Professional):
        # Soft delete: mark as inactive/deactivated instead of removing rows
        instance.deactivate("desativado via API")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"detail": "Profissional desativado."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reativar")
    def reactivate(self, request, pk=None):
        prof = self.get_object()
        prof.reactivate()
        return Response({"detail": "Profissional reativado."})

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
            except Exception as e:
                # Converte qualquer erro inesperado em 400 para evitar 500 no cliente
                return Response({"detail": str(e)}, status=400)
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
                {
                    "detail": str(exc),
                    "bot_configured": False,
                },
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
        ts = payload.get("ts")
        if not isinstance(pid, int) or pid != user.id:
            return Response({"detail": "Token não pertence ao usuário logado."}, status=403)
        if not isinstance(ts, int):
            return Response({"detail": "Token inválido."}, status=400)

        now_ts = int(timezone.now().timestamp())
        if now_ts - ts > TELEGRAM_LINK_TOKEN_TTL_SECONDS:
            return Response({"detail": "Token expirado. Gere um novo vínculo."}, status=400)

        client = TelegramBotClient()
        if not client.is_configured:
            return Response(
                {
                    "detail": "Bot do Telegram não configurado no servidor.",
                    "linked": False,
                },
                status=503,
            )

        try:
            updates = client.get_updates(limit=100, timeout=0, allowed_updates=["message"])
        except TelegramDeliveryError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "linked": False,
                },
                status=502,
            )

        matched_chat_id = None
        matched_username = ""
        expected_start = f"/start {token}"

        for update in reversed(updates):
            message = update.get("message") if isinstance(update, dict) else None
            if not isinstance(message, dict):
                continue
            text = str(message.get("text") or "").strip()
            if text != expected_start:
                continue
            chat = message.get("chat")
            if not isinstance(chat, dict):
                continue
            chat_id = chat.get("id")
            if chat_id is None:
                continue
            matched_chat_id = str(chat_id)
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

        TelegramProfessionalLink.objects.update_or_create(
            professional_id=user.id,
            defaults={
                "chat_id": matched_chat_id,
                "telegram_username": matched_username,
                "is_active": True,
                "last_error": "",
            },
        )

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

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Permite ao profissional autenticado visualizar/atualizar seu próprio perfil.
        GET: retorna first_name, last_name, register_number, id, email
        PATCH: atualiza campos permitidos (first_name, last_name, register_number)
        """
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        if request.method.lower() == "get":
            return Response(ProfessionalBasicSerializer(user).data)
        allowed_fields = {"first_name", "last_name", "register_number", "ui_theme"}
        payload = {k: v for k, v in request.data.items() if k in allowed_fields}
        if not payload:
            return Response({"detail": "No allowed fields to update."}, status=400)
        for k, v in payload.items():
            setattr(user, k, v)
        user.save(update_fields=list(payload.keys()))
        return Response(ProfessionalBasicSerializer(user).data)


class ProfessionalBasicViewSet(ReadOnlyModelViewSet):
    serializer_class = ProfessionalBasicSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # Oculta superusuários da lista pública de profissionais (não exibir no menu de login)
        return Professional.objects.filter(is_superuser=False, is_active=True)
