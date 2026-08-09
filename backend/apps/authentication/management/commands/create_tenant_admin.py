"""
Cria ou atualiza um admin de tenant (Clinic ou Bakery) de forma explícita.

Uso:
  # Clinic — cria profissional, tenant e membership
  python manage.py create_tenant_admin \\
      --email regiane@clinica.com --password Senha123 \\
      --first-name Regiane --last-name Cristina \\
      --ecosystem clinic --specialty Podologia \\
      --tenant-name "Clínica Regiane" --tenant-slug clinica-regiane

  # Bakery — idem, com alias de login
  python manage.py create_tenant_admin \\
      --email panificadora@email.com --password Senha123 \\
      --first-name Admin --last-name Panificadora \\
      --ecosystem bakery \\
      --tenant-name "Padaria Basso" --tenant-slug padaria-basso \\
      --login-alias panificadora
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.authentication.models import Professional, Tenant, TenantMembership

# Mapa especialidade → capabilities adicionais para Clinic
_SPECIALTY_CAPABILITY_MAP: list[tuple[tuple[str, ...], str]] = [
    (("odonto", "dent", "ortodont"), "odonto"),
    (("podolog",), "podologia"),
]


def _capabilities_for_specialty(specialty: str) -> dict[str, bool]:
    normalized = (specialty or "").strip().lower()
    caps: dict[str, bool] = {"clinic": True}
    for tokens, capability in _SPECIALTY_CAPABILITY_MAP:
        if any(token in normalized for token in tokens):
            caps[capability] = True
    return caps


class Command(BaseCommand):
    help = "Cria ou atualiza um admin (owner) de tenant — Clinic ou Bakery."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--first-name", required=True, dest="first_name")
        parser.add_argument("--last-name", required=True, dest="last_name")
        parser.add_argument(
            "--ecosystem",
            required=True,
            choices=["clinic", "bakery"],
        )
        parser.add_argument("--specialty", default="", help="Apenas para ecosystem=clinic")
        parser.add_argument("--tenant-name", required=True, dest="tenant_name")
        parser.add_argument("--tenant-slug", default="", dest="tenant_slug")
        parser.add_argument("--login-alias", default="", dest="login_alias", help="Alias de login no tenant (Bakery)")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        first_name = options["first_name"].strip()
        last_name = options["last_name"].strip()
        ecosystem = options["ecosystem"]
        specialty = options["specialty"].strip()
        tenant_name = options["tenant_name"].strip()
        tenant_slug = options["tenant_slug"].strip() or slugify(tenant_name)
        login_alias = options["login_alias"].strip().lower()

        if not password:
            raise CommandError("--password não pode estar vazio.")

        # Capabilities
        if ecosystem == "clinic":
            capabilities = _capabilities_for_specialty(specialty)
        else:
            capabilities = {"bakery": True}

        # Professional
        professional, created = Professional.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "specialty": specialty,
                "is_active": True,
                "is_staff": False,
            },
        )
        if not created:
            self.stdout.write(f"  Professional já existe: {email}")
        professional.set_password(password)
        professional.save(update_fields=["password"])

        # Tenant
        tenant, t_created = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                "name": tenant_name,
                "ecosystem": ecosystem,
                "capabilities": capabilities,
                "is_active": True,
            },
        )
        if not t_created:
            # Atualiza capabilities caso especialidade mude
            if tenant.capabilities != capabilities:
                tenant.capabilities = capabilities
                tenant.save(update_fields=["capabilities"])
            self.stdout.write(f"  Tenant já existe: {tenant_slug}")

        # TenantMembership
        membership, m_created = TenantMembership.objects.get_or_create(
            tenant=tenant,
            professional=professional,
            defaults={
                "role": TenantMembership.Role.OWNER,
                "login_alias": login_alias,
                "is_active": True,
            },
        )
        if not m_created:
            updates = []
            if membership.role != TenantMembership.Role.OWNER:
                membership.role = TenantMembership.Role.OWNER
                updates.append("role")
            if login_alias and membership.login_alias != login_alias:
                membership.login_alias = login_alias
                updates.append("login_alias")
            if not membership.is_active:
                membership.is_active = True
                updates.append("is_active")
            if updates:
                membership.save(update_fields=updates)

        action = "criado" if created else "atualizado"
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Admin {action}: {email}\n"
            f"   Tenant: {tenant_name} ({tenant_slug}) | ecosystem={ecosystem}\n"
            f"   Capabilities: {capabilities}\n"
            f"   Login alias: {login_alias or '(não definido)'}\n"
            f"   Role: owner\n"
        ))
