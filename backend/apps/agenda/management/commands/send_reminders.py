"""Management command: send Telegram reminders for upcoming appointments.

Run this every 5 minutes via cron:
    */5 * * * * /path/to/.venv/bin/python manage.py send_reminders

This command is kept under agenda only as a stable entrypoint. Delivery logic
now lives in apps.reminders.
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.reminders.services.reminders import dispatch_due_reminders


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envia lembretes Telegram para agendamentos próximos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--professional-email",
            default=None,
            help="Filtra o envio para uma profissional específica.",
        )
        parser.add_argument(
            "--appointment-id",
            type=int,
            default=None,
            help="Força o envio para um agendamento específico, ignorando a janela de horário.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Monta os lembretes sem chamar a API do Telegram.",
        )

    def handle(self, *args, **options):
        if not settings.APPOINTMENT_REMINDERS_ENABLED:
            self.stdout.write(
                "send_reminders (desativado) -> reminders globais desligados por APPOINTMENT_REMINDERS_ENABLED=false"
            )
            return

        try:
            summary = dispatch_due_reminders(
                professional_email=options["professional_email"],
                appointment_id=options["appointment_id"],
                dry_run=options["dry_run"],
            )
        except Exception as exc:  # pragma: no cover - defensive guard for cron runtime
            logger.exception("Falha inesperada na execução do send_reminders: %s", exc)
            self.stdout.write(
                self.style.ERROR(
                    f"send_reminders (erro) -> falha inesperada: {exc}"
                )
            )
            return

        mode = "dry-run" if options["dry_run"] else "execução"
        self.stdout.write(
            f"send_reminders ({mode}) -> processados={summary.processed} enviados={summary.sent} falhas={summary.failed} ignorados={summary.skipped}"
        )
