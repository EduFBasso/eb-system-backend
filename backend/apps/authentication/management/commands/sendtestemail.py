from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Envia um e-mail de teste usando a configuracao SMTP atual.'

    def add_arguments(self, parser):
        parser.add_argument('recipient')
        parser.add_argument(
            '--subject',
            default='Teste de e-mail - eb-system backend',
        )

    def handle(self, *args, **options):
        recipient = options['recipient'].strip()
        if not recipient:
            raise CommandError('Informe o destinatario do teste de e-mail.')

        subject = options['subject']
        from_email = settings.DEFAULT_FROM_EMAIL
        message = (
            'Este e-mail confirma que a configuracao SMTP do eb-system backend '
            'esta operacional.'
        )

        sent = send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=False,
        )
        if sent != 1:
            raise CommandError('O envio do e-mail de teste nao retornou sucesso.')

        self.stdout.write(
            self.style.SUCCESS(
                f'E-mail de teste enviado com sucesso para {recipient} via {from_email}.'
            )
        )