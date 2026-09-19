from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.clinic.models.agenda import Appointment
from apps.authentication.models import ProfessionalSettings
from apps.clinic.models.reminders import ReminderDelivery
from apps.notifications.models import TelegramProfessionalLink
from apps.notifications.services.telegram_client import (
    TelegramBotClient,
    TelegramDeliveryError,
    masked_token_fingerprint,
    resolve_bot_token,
)


logger = logging.getLogger(__name__)


# Allow slight scheduler drift so a once-per-minute loop does not miss
# reminders that become due a few seconds before the next execution.
REMINDER_DISPATCH_TOLERANCE = timedelta(minutes=2)

# Allow the first dispatches after work start to notify the first appointment
# of the day when its ideal reminder time happened overnight.
WORK_START_RETROACTIVE_GRACE = timedelta(minutes=15)


@dataclass
class DispatchSummary:
    processed: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0



def _is_auth_error(message: str) -> bool:
    normalized = (message or '').lower()
    return (
        '401' in normalized
        or '403' in normalized
        or 'unauthorized' in normalized
        or 'forbidden' in normalized
    )


def _get_work_window_bounds(now, prof_settings: ProfessionalSettings):
    local_now = timezone.localtime(now)
    work_start = local_now.replace(
        hour=prof_settings.work_start_hour,
        minute=prof_settings.work_start_minute,
        second=0,
        microsecond=0,
    )
    if prof_settings.work_end_hour == 24:
        work_end = local_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(days=1)
    else:
        work_end = local_now.replace(
            hour=prof_settings.work_end_hour,
            minute=prof_settings.work_end_minute,
            second=0,
            microsecond=0,
        )
    return local_now, work_start, work_end


def _is_within_work_window(now, prof_settings: ProfessionalSettings) -> bool:
    local_now, work_start, work_end = _get_work_window_bounds(now, prof_settings)
    return work_start <= local_now < work_end


def _get_catch_up_window_end(now, prof_settings: ProfessionalSettings):
    local_now, work_start, _ = _get_work_window_bounds(now, prof_settings)
    catch_up_window_end = work_start + timedelta(
        minutes=prof_settings.reminder_minutes_before
    )
    if local_now >= catch_up_window_end:
        return None
    return catch_up_window_end


def _format_client_name(appointment: Appointment) -> str:
    return f"{appointment.client.first_name} {appointment.client.last_name}".strip()


def _format_professional_name(appointment: Appointment) -> str:
    professional = appointment.professional
    return professional.display_name or professional.first_name or str(professional)


def _build_visit_reminder_phrase(appointment: Appointment) -> str:
    visit_type = appointment.visit_type
    if visit_type == Appointment.VisitType.CONSULTA:
        return "da sua consulta"
    if visit_type == Appointment.VisitType.RETORNO:
        return "do seu retorno"
    return "do seu atendimento"


def build_whatsapp_prefilled_text(appointment: Appointment) -> str:
    visit_reminder_phrase = _build_visit_reminder_phrase(appointment)
    professional_name = _format_professional_name(appointment).strip()
    local_start = timezone.localtime(appointment.start_at)
    date_label = local_start.strftime("%d/%m/%Y")
    time_label = local_start.strftime("%H:%M")
    return (
        f"Olá! Passando para lembrar {visit_reminder_phrase} agendado(a) "
        f"para {date_label} às {time_label}, com {professional_name}. "
        "Posso contar com sua presença?"
    )


def build_whatsapp_url(appointment: Appointment) -> str | None:
    raw_phone = getattr(appointment.client, "phone", "") or ""
    digits = "".join(char for char in str(raw_phone) if char.isdigit())
    if not digits:
        return None
    if not digits.startswith("55"):
        digits = "55" + digits

    query = urlencode({"text": build_whatsapp_prefilled_text(appointment)})
    return f"https://wa.me/{digits}?{query}"


def build_telegram_text(appointment: Appointment) -> str:
    visit_type_label = appointment.get_visit_type_display()
    local_start = timezone.localtime(appointment.start_at)
    lines = [
        "Lembrete de compromisso",
        "",
        f"Cliente: {_format_client_name(appointment)}",
        f"Tipo: {visit_type_label}",
        f"Horário: {local_start.strftime('%d/%m/%Y às %H:%M')}",
    ]
    if appointment.location:
        lines.append(f"Local: {appointment.location}")
    if appointment.notes:
        lines.extend(["", f"Obs.: {appointment.notes.strip()}"])
    lines.extend(["", "Abra a conversa no WhatsApp pelo botão abaixo."])
    return "\n".join(lines)


def build_reply_markup(appointment: Appointment) -> dict | None:
    whatsapp_url = build_whatsapp_url(appointment)
    if not whatsapp_url:
        return None
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Abrir conversa no WhatsApp",
                    "url": whatsapp_url,
                }
            ]
        ]
    }


def get_due_appointments(*, now=None, professional_email: str | None = None):
    if not settings.APPOINTMENT_REMINDERS_ENABLED:
        return

    now = now or timezone.now()
    prof_settings_qs = ProfessionalSettings.objects.filter(
        reminder_enabled=True,
        professional__is_active=True,
    ).select_related("professional")
    if professional_email:
        prof_settings_qs = prof_settings_qs.filter(
            professional__email__iexact=professional_email
        )

    for prof_settings in prof_settings_qs:
        if not _is_within_work_window(now, prof_settings):
            continue

        trigger_window_end = now + timedelta(
            minutes=prof_settings.reminder_minutes_before
        )
        trigger_window_start = trigger_window_end - REMINDER_DISPATCH_TOLERANCE
        appointment_filters = Q(
            start_at__gte=trigger_window_start,
            start_at__lte=trigger_window_end,
        )

        catch_up_window_end = _get_catch_up_window_end(now, prof_settings)
        if catch_up_window_end is not None:
            local_now, work_start, _ = _get_work_window_bounds(now, prof_settings)
            catch_up_window_start = work_start
            retroactive_floor = local_now - WORK_START_RETROACTIVE_GRACE
            if retroactive_floor > catch_up_window_start:
                catch_up_window_start = retroactive_floor

            # Reminders that became due before work start stay queued until the
            # professional enters the next work window. A short grace window
            # right after opening also covers the first appointment of the day.
            appointment_filters |= Q(
                start_at__gte=catch_up_window_start,
                start_at__lte=catch_up_window_end,
            )

        appointments = (
            Appointment.objects.filter(
                professional=prof_settings.professional,
                status=Appointment.Status.SCHEDULED,
                reminder_sent=False,
            )
            .filter(appointment_filters)
            .select_related("client", "professional")
            .prefetch_related("professional__telegram_link")
            .order_by("start_at")
            .distinct()
        )
        for appointment in appointments:
            yield appointment


def dispatch_appointment_reminder(
    appointment: Appointment,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> ReminderDelivery | None:
    if not settings.APPOINTMENT_REMINDERS_ENABLED:
        return ReminderDelivery.objects.create(
            tenant=appointment.tenant,
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SKIPPED,
            error_message="Lembretes desativados globalmente.",
            payload={"reason": "feature_disabled"},
        )

    appointment = Appointment.objects.select_related("professional", "client").get(
        pk=appointment.pk
    )

    if appointment.reminder_sent and not force:
        return ReminderDelivery.objects.create(
            tenant=appointment.tenant,
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SKIPPED,
            error_message="Lembrete já enviado anteriormente.",
            payload={"reason": "already_sent"},
        )

    try:
        link = appointment.professional.telegram_link
    except TelegramProfessionalLink.DoesNotExist:
        return ReminderDelivery.objects.create(
            tenant=appointment.tenant,
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SKIPPED,
            error_message="Profissional sem vínculo ativo no Telegram.",
            payload={"reason": "telegram_not_linked"},
        )

    if not link.is_active:
        return ReminderDelivery.objects.create(
            tenant=appointment.tenant,
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SKIPPED,
            error_message="Vínculo do Telegram está inativo.",
            payload={"reason": "telegram_inactive"},
        )

    resolved_token, bot_origin = resolve_bot_token(link)
    resolved_client = TelegramBotClient(token=resolved_token)

    payload = {
        "text": build_telegram_text(appointment),
        "reply_markup": build_reply_markup(appointment) or {},
        "bot_origin": bot_origin,
        "bot_token_fingerprint": masked_token_fingerprint(resolved_token),
    }

    if dry_run:
        logger.info(
            "[dry-run] Reminder Telegram para appointment=%s profissional=%s",
            appointment.pk,
            appointment.professional.email,
        )
        return None

    try:
        send_result = resolved_client.send_message(
            chat_id=link.chat_id,
            text=payload["text"],
            reply_markup=payload["reply_markup"] or None,
        )
    except TelegramDeliveryError as exc:
        auth_error = _is_auth_error(str(exc))
        link.last_error = str(exc)
        link.save(update_fields=["last_error", "updated_at"])
        return ReminderDelivery.objects.create(
            tenant=appointment.tenant,
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.FAILED,
            error_message=(
                "Falha de autenticação no bot privado do profissional. "
                "Token global não foi usado como fallback."
                if bot_origin == 'professional' and auth_error
                else str(exc)
            ),
            payload=payload,
        )

    link.last_error = ""
    link.save(update_fields=["last_error", "updated_at"])
    with transaction.atomic():
        delivery = ReminderDelivery.objects.create(
            tenant=appointment.tenant,
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SENT,
            sent_at=timezone.now(),
            payload=payload,
            response_payload=send_result.raw,
            external_message_id=send_result.message_id,
        )
        appointment.reminder_sent = True
        appointment.save(update_fields=["reminder_sent"])
    return delivery


def dispatch_due_reminders(
    *,
    now=None,
    professional_email: str | None = None,
    appointment_id: int | None = None,
    dry_run: bool = False,
) -> DispatchSummary:
    summary = DispatchSummary()
    if not settings.APPOINTMENT_REMINDERS_ENABLED:
        return summary

    if appointment_id is not None:
        appointments = Appointment.objects.filter(pk=appointment_id).select_related(
            "professional", "client"
        ).prefetch_related("professional__telegram_link")
    else:
        appointments = get_due_appointments(
            now=now,
            professional_email=professional_email,
        )

    for appointment in appointments:
        summary.processed += 1
        try:
            delivery = dispatch_appointment_reminder(
                appointment,
                dry_run=dry_run,
                force=appointment_id is not None,
            )
            if delivery is None:
                continue
            if delivery.status == ReminderDelivery.Status.SENT:
                summary.sent += 1
            elif delivery.status == ReminderDelivery.Status.FAILED:
                summary.failed += 1
            else:
                summary.skipped += 1
        except Exception as exc:  # pragma: no cover - defensive hardening for cron runtime
            logger.exception(
                "Erro inesperado ao enviar lembrete appointment_id=%s professional_id=%s: %s",
                appointment.pk,
                appointment.professional_id,
                exc,
            )
            summary.failed += 1

    if summary.processed == 0:
        logger.info(
            "Nenhum lembrete elegível encontrado (professional_email=%s appointment_id=%s).",
            professional_email,
            appointment_id,
        )
    return summary