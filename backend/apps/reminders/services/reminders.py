from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.agenda.models import Appointment
from apps.register.models import ProfessionalSettings
from apps.reminders.models import ReminderDelivery, TelegramProfessionalLink
from apps.reminders.services.telegram import TelegramBotClient, TelegramDeliveryError


logger = logging.getLogger(__name__)


# Allow slight scheduler drift so a once-per-minute loop does not miss
# reminders that become due a few seconds before the next execution.
REMINDER_DISPATCH_TOLERANCE = timedelta(minutes=2)


@dataclass
class DispatchSummary:
    processed: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0


def _format_client_name(appointment: Appointment) -> str:
    return f"{appointment.client.first_name} {appointment.client.last_name}".strip()


def _format_professional_name(appointment: Appointment) -> str:
    professional = appointment.professional
    return professional.display_name or professional.first_name or str(professional)


def _build_visit_reminder_phrase(appointment: Appointment) -> str:
    visit_type = appointment.visit_type
    if visit_type == Appointment.VisitType.CONSULTA:
        return "da sua consulta"
    if visit_type == Appointment.VisitType.AVALIACAO:
        return "da sua avaliação"
    if visit_type == Appointment.VisitType.RETORNO:
        return "do seu retorno"
    if visit_type == Appointment.VisitType.PROCEDIMENTO:
        return "do seu procedimento"
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
        trigger_window_end = now + timedelta(
            minutes=prof_settings.reminder_minutes_before
        )
        trigger_window_start = trigger_window_end - REMINDER_DISPATCH_TOLERANCE

        appointments = (
            Appointment.objects.filter(
                professional=prof_settings.professional,
                status=Appointment.Status.SCHEDULED,
                start_at__gte=trigger_window_start,
                start_at__lte=trigger_window_end,
                reminder_sent=False,
            )
            .select_related("client", "professional")
            .order_by("start_at")
        )
        for appointment in appointments:
            yield appointment


def dispatch_appointment_reminder(
    appointment: Appointment,
    *,
    client: TelegramBotClient | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> ReminderDelivery | None:
    if not settings.APPOINTMENT_REMINDERS_ENABLED:
        return ReminderDelivery.objects.create(
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SKIPPED,
            error_message="Lembretes desativados globalmente.",
            payload={"reason": "feature_disabled"},
        )

    client = client or TelegramBotClient()
    appointment = Appointment.objects.select_related("professional", "client").get(
        pk=appointment.pk
    )

    if appointment.reminder_sent and not force:
        return ReminderDelivery.objects.create(
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
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SKIPPED,
            error_message="Profissional sem vínculo ativo no Telegram.",
            payload={"reason": "telegram_not_linked"},
        )

    if not link.is_active:
        return ReminderDelivery.objects.create(
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.SKIPPED,
            error_message="Vínculo do Telegram está inativo.",
            payload={"reason": "telegram_inactive"},
        )

    payload = {
        "text": build_telegram_text(appointment),
        "reply_markup": build_reply_markup(appointment) or {},
    }

    if dry_run:
        logger.info(
            "[dry-run] Reminder Telegram para appointment=%s profissional=%s",
            appointment.pk,
            appointment.professional.email,
        )
        return None

    try:
        send_result = client.send_message(
            chat_id=link.chat_id,
            text=payload["text"],
            reply_markup=payload["reply_markup"] or None,
        )
    except TelegramDeliveryError as exc:
        link.last_error = str(exc)
        link.save(update_fields=["last_error", "updated_at"])
        return ReminderDelivery.objects.create(
            appointment=appointment,
            professional=appointment.professional,
            channel=ReminderDelivery.Channel.TELEGRAM,
            status=ReminderDelivery.Status.FAILED,
            error_message=str(exc),
            payload=payload,
        )

    link.last_error = ""
    link.save(update_fields=["last_error", "updated_at"])
    with transaction.atomic():
        delivery = ReminderDelivery.objects.create(
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

    client = TelegramBotClient()

    if appointment_id is not None:
        appointments = Appointment.objects.filter(pk=appointment_id).select_related(
            "professional", "client"
        )
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
                client=client,
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