# backend/apps/authentication/management/commands/create_tenant_admin.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.authentication.models.register_models import Professional
from apps.authentication.models.tenancy_models import Tenant, TenantMembership

# Mapa de especialidades clínicas para ativar módulos dinâmicos (Capabilities)
_SPECIALTY_CAPABILITY_MAP: list[tuple[tuple[str, ...], str]] = [
    (("odonto", "dent", "ortodont"), "odonto"),
    (("podolog",), "podologia"),
]


def _capabilities_for_specialty(specialty: str) -> dict[str, bool]:
    normalized = (specialty or "").strip().lower()
    # Ativa por padrão a capacidade base de clínica
    caps: dict[str, bool] = {"clinic": True}
    for tokens, capability in _SPECIALTY_CAPABILITY_MAP:
        if any(token in normalized for token in tokens):
            caps[capability] = True
    return caps


def _normalize_secret_token(value: str) -> str:
    return ''.join(ch for ch in (value or '').lower() if ch.isalnum())


def _password_uses_identity(raw_password: str, *, email: str, first_name: str, last_name: str, login_alias: str) -> bool:
    """[Segurança] Impede senhas óbvias baseadas em dados cadastrais do próprio usuário."""
    normalized_password = _normalize_secret_token(raw_password)
    if not normalized_password:
        return False

    local_part = (email or '').split('@')[0]
    full_name = f"{first_name} {last_name}".strip()
    candidates = [first_name, last_name, full_name, email, local_part, login_alias]
    normalized_candidates = {_normalize_secret_token(item) for item in candidates if item}
    return normalized_password in normalized_candidates


def _has_duplicate_bakery_owner_name(first_name: str, last_name: str, current_professional_id: int | None) -> bool:
    """Impede donos de Padarias com nomes idênticos no mesmo ecossistema."""
    queryset = TenantMembership.objects.filter(
        tenant__ecosystem=Tenant.Ecosystem.BAKERY,
        role=TenantMembership.Role.OWNER,
        professional__first_name__iexact=(first_name or '').strip(),
        professional__last_name__iexact=(last_name or '').strip(),
    )
    if current_professional_id is not None:
        queryset = queryset.exclude(professional_id=current_professional_id)
    return queryset.exists()


def _is_password_reused(raw_password: str, current_user: Professional | None = None) -> bool:
    """[Segurança] Impede que profissionais compartilhem exatamente a mesma senha."""
    queryset = Professional.objects.all()
    if current_user and current_user.pk:
        queryset = queryset.exclude(pk=current_user.pk)
    for professional in queryset.iterator():
        if professional.has_usable_password() and professional.check_password(raw_password):
            return True
    return False


class Command(BaseCommand):
    help = "Cria ou atualiza uma conta de Administrador/Proprietário (Owner) vinculada a um Tenant."

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
        parser.add_argument("--specialty", default="", help="Especialidade médica (Apenas para ecosystem=clinic)")
        parser.add_argument("--tenant-name", required=True, dest="tenant_name")
        parser.add_argument("--tenant-slug", default="", dest="tenant_slug")
        parser.add_argument("--login-alias", default="", dest="login_alias", help="Apelido de login rápido")

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
            raise CommandError("O parâmetro --password é obrigatório e não pode ser nulo.")

        if _password_uses_identity(
            password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            login_alias=login_alias,
        ):
            raise CommandError("Segurança: A senha não pode conter seu nome, sobrenome, e-mail ou apelido.")

        # Define as capacidades do Tenant baseadas no ecossistema selecionado
        if ecosystem == "clinic":
            capabilities = _capabilities_for_specialty(specialty)
        else:
            capabilities = {"bakery": True}

        # 1. Criação/Recuperação do Usuário Profissional
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
            self.stdout.write(self.style.WARNING(f"  Profissional já existente na plataforma: {email}"))

        if ecosystem == "bakery" and _has_duplicate_bakery_owner_name(
            first_name,
            last_name,
            current_professional_id=professional.id,
        ):
            raise CommandError("Já existe um proprietário registrado na rede de Padarias com este mesmo nome.")

        if _is_password_reused(password, current_user=professional):
            raise CommandError("Esta senha já está sendo utilizada por outra conta no sistema.")

        # Criptografa e atualiza a senha de acesso
        professional.set_password(password)
        professional.save(update_fields=["password"])

        # 2. Criação/Recuperação da Empresa (Tenant)
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
            # Validação crucial de segurança multi-tenant
            if tenant.ecosystem != ecosystem:
                raise CommandError(f"Conflito de Slugs: O slug '{tenant_slug}' já pertence ao ecossistema {tenant.ecosystem}.")
                
            # Atualiza as capacidades dinâmicas caso a especialidade da clínica mude
            if tenant.capabilities != capabilities:
                tenant.capabilities = capabilities
                tenant.save(update_fields=["capabilities"])
            self.stdout.write(self.style.WARNING(f"  Empresa (Tenant) já existente no sistema: {tenant_slug}"))

        # 3. Vinculação de Controle e Governança (TenantMembership)
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
                
        self.stdout.write(self.style.SUCCESS(f"Sucesso: Admin Owner configurado para {email} no Tenant {tenant_slug}."))

        # action = "criado" if created else "atualizado"
        # self.stdout.write(self.style.SUCCESS(
        #     f"\n✅ Admin {action}: {email}\n"
        #     f"   Tenant: {tenant_name} ({tenant_slug}) | ecosystem={ecosystem}\n"
        #     f"   Capabilities: {capabilities}\n"
        #     f"   Login alias: {login_alias or '(não definido)'}\n"
        #     f"   Role: owner\n"
        # ))
