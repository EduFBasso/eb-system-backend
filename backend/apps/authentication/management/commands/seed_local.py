from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional


class Command(BaseCommand):
    help = "Seed local development data: one Professional and some Clients"

    def add_arguments(self, parser):
        parser.add_argument('--email', default='dev@example.com')
        parser.add_argument('--password', default='dev123')
        parser.add_argument('--first', dest='first_name', default='Dev')
        parser.add_argument('--last', dest='last_name', default='User')
        parser.add_argument('--clients', type=int, default=6)

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        num_clients = options['clients']
        first_name = options['first_name']
        last_name = options['last_name']

        prof, created = Professional.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'register_number': 'DEV-000',
                'specialty': 'Podologia',
                'is_active': True,
            }
        )
        if created:
            prof.set_password(password)
            prof.save(update_fields=['password'])
            self.stdout.write(self.style.SUCCESS(f"Professional created: {email} / {password}"))
        else:
            # Ensure password is set on existing user for convenience
            prof.set_password(password)
            prof.save(update_fields=['password'])
            self.stdout.write(self.style.WARNING(f"Professional existed; password reset: {email} / {password}"))

        # Create sample clients linked to this professional
        first_names = [
            'Ana', 'Bruno', 'Carla', 'Daniel', 'Eva', 'Felipe', 'Giovana', 'Henrique', 'Isabela', 'João'
        ]
        created_count = 0
        for i in range(num_clients):
            fn = first_names[i % len(first_names)]
            ln = f"Teste{i+1}"
            phone = f"+55119999{i:04d}"

            client, c_created = Client.objects.get_or_create(
                professional=prof,
                phone=phone,
                defaults={
                    'first_name': fn,
                    'last_name': ln,
                    'city': 'São Paulo',
                    'state': 'SP',
                }
            )
            created_count += 1 if c_created else 0

        self.stdout.write(self.style.SUCCESS(f"Clients ready (created {created_count}, total requested {num_clients})."))
        self.stdout.write(self.style.SUCCESS("Seeding done."))
