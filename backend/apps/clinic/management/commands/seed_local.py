from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.authentication.models.register_models import Professional
from apps.authentication.models.tenancy_models import Tenant, TenantMembership
from apps.clinic.models.clients import Client


class Command(BaseCommand):
    help = "Gera massa de dados inicial rápida para o ambiente de desenvolvimento local (Tenant + Profissional + Clientes)"

    def add_arguments(self, parser):
        parser.add_argument("--email", default="dev@example.com")
        parser.add_argument("--password", default="dev123")
        parser.add_argument("--first", dest="first_name", default="Dev")
        parser.add_argument("--last", dest="last_name", default="User")
        parser.add_argument("--tenant-name", default="Clínica Desenvolvimento Local", dest="tenant_name")
        parser.add_argument("--clients", type=int, default=6)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        num_clients = options["clients"]
        first_name = options["first_name"]
        last_name = options["last_name"]
        tenant_name = options["tenant_name"].strip()
        tenant_slug = slugify(tenant_name) or "clinica-dev-local"

        tenant, _ = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                "name": tenant_name,
                "ecosystem": Tenant.Ecosystem.CLINIC,
                "capabilities": {"clinic": True, "podologia": True},
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Tenant pronto: {tenant.name} ({tenant.slug})"))

        professional, created = Professional.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "register_number": "DEV-000",
                "specialty": "Podologia",
                "is_active": True,
            },
        )
        professional.set_password(password)
        professional.save(update_fields=["password"])

        message = "Professional dev criado" if created else "Professional já existente; senha redefinida"
        self.stdout.write(self.style.SUCCESS(f"{message}: {email} / {password}"))

        TenantMembership.objects.get_or_create(
            tenant=tenant,
            professional=professional,
            defaults={"role": TenantMembership.Role.OWNER, "is_active": True},
        )

        first_names = ["Ana", "Bruno", "Carla", "Daniel", "Eva", "Felipe", "Giovana", "Henrique", "Isabela", "João"]
        created_count = 0
        for index in range(num_clients):
            client, client_created = Client.objects.get_or_create(
                tenant=tenant,
                phone=f"+55119999{index:04d}",
                defaults={
                    "first_name": first_names[index % len(first_names)],
                    "last_name": f"Teste{index + 1}",
                    "city": "São Paulo",
                    "state": "SP",
                },
            )
            created_count += int(client_created)

        self.stdout.write(self.style.SUCCESS(
            f"Clientes locais prontos (criados: {created_count}, requisitados: {num_clients})."
        ))
        self.stdout.write(self.style.SUCCESS("🚀 Seed de ambiente de desenvolvimento local concluído com sucesso total."))
