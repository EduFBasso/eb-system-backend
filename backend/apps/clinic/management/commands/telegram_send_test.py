from django.core.management.base import BaseCommand, CommandError

from apps.authentication.models import Professional
from apps.clinic.services.telegram import TelegramBotClient, TelegramDeliveryError


class Command(BaseCommand):
    help = "Envia uma mensagem de teste para o Telegram do profissional."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument(
            "--message",
            default="Teste de lembrete do Clinic System via Telegram.",
        )

    def handle(self, *args, **options):
        try:
            professional = Professional.objects.select_related("telegram_link").get(
                email__iexact=options["email"]
            )
        except Professional.DoesNotExist as exc:
            raise CommandError("Profissional não encontrado.") from exc

        try:
            link = professional.telegram_link
        except Exception as exc:
            raise CommandError("Profissional sem vínculo Telegram.") from exc

        client = TelegramBotClient()
        try:
            result = client.send_message(chat_id=link.chat_id, text=options["message"])
        except TelegramDeliveryError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Mensagem enviada com sucesso. message_id={result.message_id}"
            )
        )