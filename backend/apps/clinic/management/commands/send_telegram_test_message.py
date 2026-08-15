from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from apps.authentication.models import Professional
from apps.clinic.services.reminders import _masked_token_fingerprint, _resolve_bot_token
from apps.clinic.services.telegram import TelegramBotClient, TelegramDeliveryError


class Command(BaseCommand):
    help = "Envia uma mensagem de teste para o Telegram usando roteamento dinâmico de token."

    def add_arguments(self, parser):
        parser.add_argument(
            "--professional-email",
            required=False,
            help="E-mail do profissional para usar o chat_id do vínculo Telegram e token dinâmico.",
        )
        parser.add_argument(
            "--email",
            required=False,
            help="Alias legado de --professional-email.",
        )
        parser.add_argument(
            "--chat-id",
            required=False,
            help="Chat ID de destino quando não for informado --professional-email.",
        )
        parser.add_argument(
            "--message",
            default="Teste de lembrete do Clinic System via Telegram.",
        )

    def handle(self, *args, **options):
        professional_email = options.get("professional_email") or options.get("email")
        message = options["message"]
        chat_id = options.get("chat_id")
        token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
        bot_origin = "global"

        if professional_email:
            try:
                professional = Professional.objects.select_related("telegram_link").get(
                    email__iexact=professional_email
                )
            except Professional.DoesNotExist as exc:
                raise CommandError("Profissional não encontrado.") from exc

            try:
                link = professional.telegram_link
            except Exception as exc:
                raise CommandError("Profissional sem vínculo Telegram.") from exc

            token, bot_origin = _resolve_bot_token(link)
            chat_id = link.chat_id

        if not chat_id:
            raise CommandError(
                "Informe --chat-id ou use --professional-email para resolver o chat de destino."
            )

        client = TelegramBotClient(
            token=token,
            api_base=settings.TELEGRAM_BOT_API_BASE,
            timeout=settings.TELEGRAM_BOT_TIMEOUT_SECONDS,
        )
        try:
            result = client.send_message(chat_id=chat_id, text=message)
        except TelegramDeliveryError as exc:
            raise CommandError(str(exc)) from exc

        bot_kind = "Bot do Profissional" if bot_origin == "professional" else "Bot Global"
        bot_fingerprint = _masked_token_fingerprint(token)
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Mensagem enviada via {bot_kind} [{bot_fingerprint}] "
                    f"com sucesso. message_id={result.message_id}"
                )
            )
        )