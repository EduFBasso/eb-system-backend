from django.core.management.base import BaseCommand, CommandError

from apps.authentication.models import Professional
from apps.clinic.models.reminders import TelegramProfessionalLink


class Command(BaseCommand):
    help = "Cria ou atualiza o vínculo Telegram de um profissional."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--chat-id", required=True)
        parser.add_argument("--username", default="")
        parser.add_argument("--inactive", action="store_true")

    def handle(self, *args, **options):
        try:
            professional = Professional.objects.get(email__iexact=options["email"])
        except Professional.DoesNotExist as exc:
            raise CommandError("Profissional não encontrado.") from exc

        membership = (
            professional.tenant_memberships.select_related("tenant")
            .filter(is_active=True, tenant__is_active=True)
            .order_by("created_at", "id")
            .first()
        )
        if membership is None:
            raise CommandError("Profissional sem tenant ativo.")

        link, created = TelegramProfessionalLink.objects.update_or_create(
            professional=professional,
            defaults={
                "tenant": membership.tenant,
                "chat_id": options["chat_id"],
                "telegram_username": options["username"],
                "is_active": not options["inactive"],
            },
        )

        action = "criado" if created else "atualizado"
        self.stdout.write(
            self.style.SUCCESS(
                f"Vínculo Telegram {action}: {professional.email} -> {link.chat_id}"
            )
        )