from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.clinic.models.agenda import Appointment
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional, ProfessionalSettings, Tenant, TenantMembership
from apps.clinic.models.reminders import ReminderDelivery
from apps.notifications.models import TelegramProfessionalLink
from apps.clinic.services.reminders import (
    build_whatsapp_prefilled_text,
    dispatch_appointment_reminder,
    get_due_appointments,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enable_reminders(settings):
    settings.APPOINTMENT_REMINDERS_ENABLED = True


@pytest.fixture
def professional():
    pro = Professional.objects.create_user(
        email="telegram@example.com",
        password="secret123",
        first_name="Ana",
        last_name="Silva",
    )
    pro.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Reminders', slug='tenant-reminders')
    TenantMembership.objects.create(
        tenant=tenant, professional=pro,
        role=TenantMembership.Role.OWNER, is_active=True,
    )
    return pro


@pytest.fixture
def client(professional):
    return Client.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        first_name="Maria",
        last_name="Souza",
        email="maria@example.com",
        phone="11999998888",
    )


@pytest.fixture
def appointment(professional, client):
    start_at = timezone.now() + timedelta(minutes=10)
    end_at = start_at + timedelta(minutes=60)
    return Appointment.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="Consulta",
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=start_at,
        end_at=end_at,
        status=Appointment.Status.SCHEDULED,
    )


@pytest.fixture
def reminder_settings(professional):
    return ProfessionalSettings.objects.create(
        professional=professional,
        reminder_enabled=True,
        reminder_minutes_before=10,
        work_start_hour=0,
        work_start_minute=0,
        work_end_hour=24,
        work_end_minute=0,
    )


def test_dispatch_appointment_reminder_sends_telegram(
    appointment,
    reminder_settings,
    professional,
    settings,
):
    settings.TELEGRAM_BOT_TOKEN = "test-token"
    TelegramProfessionalLink.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        chat_id="123456",
        telegram_username="ana_silva",
    )

    with patch("apps.notifications.services.telegram_client.requests.post") as mocked_post:
        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 77},
        }

        delivery = dispatch_appointment_reminder(appointment)

    appointment.refresh_from_db()
    assert appointment.reminder_sent is True
    assert delivery is not None
    assert delivery.status == ReminderDelivery.Status.SENT
    assert delivery.external_message_id == "77"
    assert delivery.payload["bot_origin"] == "global"
    assert delivery.payload["bot_token_fingerprint"].endswith("oken")
    assert "Abrir conversa no WhatsApp" in str(delivery.payload)
    assert "?text=" in str(delivery.payload)
    assert "Posso+contar+com+sua+presen%C3%A7a%3F" in str(delivery.payload)
    assert mocked_post.called


def test_dispatch_appointment_reminder_uses_professional_private_bot_token(
    appointment,
    reminder_settings,
    professional,
    settings,
):
    settings.TELEGRAM_BOT_TOKEN = "global-token"
    TelegramProfessionalLink.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        chat_id="123456",
        bot_token="private-token-1234",
        telegram_username="ana_private",
    )

    with patch("apps.notifications.services.telegram_client.requests.post") as mocked_post:
        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 99},
        }

        delivery = dispatch_appointment_reminder(appointment)

    assert delivery is not None
    assert delivery.status == ReminderDelivery.Status.SENT
    assert delivery.payload["bot_origin"] == "professional"
    assert delivery.payload["bot_token_fingerprint"] == "***1234"
    called_url = mocked_post.call_args.args[0]
    assert "private-token-1234" in called_url


def test_dispatch_appointment_reminder_private_token_auth_failure_does_not_fallback(
    appointment,
    reminder_settings,
    professional,
    settings,
):
    settings.TELEGRAM_BOT_TOKEN = "global-fallback-token"
    TelegramProfessionalLink.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        chat_id="123456",
        bot_token="private-token-401x",
    )

    with patch("apps.notifications.services.telegram_client.requests.post") as mocked_post:
        mocked_post.return_value.status_code = 401
        mocked_post.return_value.json.return_value = {
            "ok": False,
            "description": "Unauthorized",
        }

        delivery = dispatch_appointment_reminder(appointment)

    appointment.refresh_from_db()
    assert appointment.reminder_sent is False
    assert delivery is not None
    assert delivery.status == ReminderDelivery.Status.FAILED
    assert "Token global não foi usado como fallback" in delivery.error_message
    assert delivery.payload["bot_origin"] == "professional"
    assert mocked_post.call_count == 1
    called_url = mocked_post.call_args.args[0]
    assert "private-token-401x" in called_url
    assert "global-fallback-token" not in called_url


def test_build_whatsapp_prefilled_text_uses_human_friendly_confirmation_copy(
    appointment,
):
    text = build_whatsapp_prefilled_text(appointment)

    assert text.startswith("Olá! Passando para lembrar da sua consulta")
    assert text.endswith("Posso contar com sua presença?")
    assert "/" in text
    assert ":" in text


def test_build_whatsapp_prefilled_text_mentions_return_visit_type_explicitly(
    appointment,
):
    appointment.visit_type = Appointment.VisitType.RETORNO

    text = build_whatsapp_prefilled_text(appointment)

    assert "do seu retorno" in text


def test_dispatch_appointment_reminder_skips_without_telegram_link(appointment, reminder_settings):
    delivery = dispatch_appointment_reminder(appointment)

    appointment.refresh_from_db()
    assert appointment.reminder_sent is False
    assert delivery is not None
    assert delivery.status == ReminderDelivery.Status.SKIPPED
    assert delivery.payload["reason"] == "telegram_not_linked"


def test_send_reminders_command_can_force_specific_appointment(
    appointment,
    professional,
    settings,
):
    settings.TELEGRAM_BOT_TOKEN = "test-token"
    TelegramProfessionalLink.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        chat_id="123456",
    )

    with patch("apps.notifications.services.telegram_client.requests.post") as mocked_post:
        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 88},
        }

        call_command(
            "send_clinic_appointment_reminders",
            "--appointment-id",
            str(appointment.pk),
        )

    appointment.refresh_from_db()
    assert appointment.reminder_sent is True
    assert ReminderDelivery.objects.filter(
        appointment=appointment,
        status=ReminderDelivery.Status.SENT,
    ).exists()


def test_get_due_appointments_does_not_send_before_threshold(
    appointment,
    reminder_settings,
):
    now = appointment.start_at - timedelta(minutes=10, seconds=10)

    due_ids = [item.id for item in get_due_appointments(now=now)]

    assert appointment.id not in due_ids


def test_get_due_appointments_sends_once_threshold_is_reached(
    appointment,
    reminder_settings,
):
    now = appointment.start_at - timedelta(minutes=10) + timedelta(seconds=10)

    due_ids = [item.id for item in get_due_appointments(now=now)]

    assert appointment.id in due_ids


def test_get_due_appointments_tolerates_scheduler_drift_after_threshold(
    appointment,
    reminder_settings,
):
    now = appointment.start_at - timedelta(minutes=10) + timedelta(minutes=1, seconds=5)

    due_ids = [item.id for item in get_due_appointments(now=now)]

    assert appointment.id in due_ids


def test_get_due_appointments_skips_dispatch_before_work_start(
    appointment,
    reminder_settings,
):
    reference = timezone.localtime(timezone.now()).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    appointment.start_at = reference.replace(hour=7, minute=0)
    appointment.end_at = reference.replace(hour=8, minute=0)
    appointment.save(update_fields=["start_at", "end_at"])

    reminder_settings.work_start_hour = 6
    reminder_settings.work_start_minute = 0
    reminder_settings.work_end_hour = 21
    reminder_settings.work_end_minute = 0
    reminder_settings.reminder_minutes_before = 90
    reminder_settings.save(
        update_fields=[
            "work_start_hour",
            "work_start_minute",
            "work_end_hour",
            "work_end_minute",
            "reminder_minutes_before",
        ]
    )

    now = reference.replace(hour=5, minute=45)

    due_ids = [item.id for item in get_due_appointments(now=now)]

    assert appointment.id not in due_ids


def test_get_due_appointments_releases_overnight_backlog_at_work_start(
    appointment,
    reminder_settings,
):
    reference = timezone.localtime(timezone.now()).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    appointment.start_at = reference.replace(hour=7, minute=0)
    appointment.end_at = reference.replace(hour=8, minute=0)
    appointment.save(update_fields=["start_at", "end_at"])

    reminder_settings.work_start_hour = 6
    reminder_settings.work_start_minute = 0
    reminder_settings.work_end_hour = 21
    reminder_settings.work_end_minute = 0
    reminder_settings.reminder_minutes_before = 90
    reminder_settings.save(
        update_fields=[
            "work_start_hour",
            "work_start_minute",
            "work_end_hour",
            "work_end_minute",
            "reminder_minutes_before",
        ]
    )

    now = reference.replace(hour=6, minute=5)

    due_ids = [item.id for item in get_due_appointments(now=now)]

    assert appointment.id in due_ids


def test_get_due_appointments_allows_first_appointment_shortly_after_opening(
    appointment,
    reminder_settings,
):
    reference = timezone.localtime(timezone.now()).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    appointment.start_at = reference.replace(hour=6, minute=0)
    appointment.end_at = reference.replace(hour=7, minute=0)
    appointment.save(update_fields=["start_at", "end_at"])

    reminder_settings.work_start_hour = 6
    reminder_settings.work_start_minute = 0
    reminder_settings.work_end_hour = 21
    reminder_settings.work_end_minute = 0
    reminder_settings.reminder_minutes_before = 180
    reminder_settings.save(
        update_fields=[
            "work_start_hour",
            "work_start_minute",
            "work_end_hour",
            "work_end_minute",
            "reminder_minutes_before",
        ]
    )

    now = reference.replace(hour=6, minute=5)

    due_ids = [item.id for item in get_due_appointments(now=now)]

    assert appointment.id in due_ids


def test_dispatch_due_reminders_is_disabled_by_global_flag(
    appointment,
    reminder_settings,
    settings,
):
    settings.APPOINTMENT_REMINDERS_ENABLED = False

    due_ids = [item.id for item in get_due_appointments(now=timezone.now())]

    assert due_ids == []