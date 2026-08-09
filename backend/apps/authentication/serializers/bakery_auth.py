from __future__ import annotations

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.bakery.models import BakeryCustomer


class BakeryTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login exclusivo do ecossistema Bakery.

    Recebe: { login, password, tenant_slug }
    - login pode ser email ou login_alias da membership naquele tenant.
    - tenant_slug identifica o tenant sem ambiguidade.
    """

    username_field = "email"

    login = serializers.CharField(write_only=True)
    tenant_slug = serializers.SlugField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove o campo 'email' padrão do TokenObtainPairSerializer
        self.fields.pop("email", None)

    def _resolve_email(self, login: str, tenant: Tenant) -> str | None:
        """Resolve login como email ou login_alias dentro do tenant."""
        if "@" in login:
            return login.strip().lower()

        # Busca por alias na membership do tenant
        membership = (
            TenantMembership.objects
            .select_related("professional")
            .filter(
                tenant=tenant,
                login_alias__iexact=login,
                is_active=True,
            )
            .first()
        )
        if membership:
            return membership.professional.email

        return None

    def validate(self, attrs):
        login = attrs.get("login", "").strip()
        password = attrs.get("password", "")
        tenant_slug = attrs.get("tenant_slug", "").strip()

        if not login or not password or not tenant_slug:
            raise serializers.ValidationError(_("login, password e tenant_slug são obrigatórios."))

        # Resolve tenant
        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True, ecosystem=Tenant.Ecosystem.BAKERY)
        except Tenant.DoesNotExist:
            raise serializers.ValidationError(_("Tenant Bakery não encontrado ou inativo."))

        # Resolve email dentro do tenant
        email = self._resolve_email(login, tenant)
        if not email:
            raise serializers.ValidationError(_("Credenciais inválidas ou usuário não encontrado."))

        # Autentica
        user = authenticate(username=email, password=password)
        if user is None:
            raise serializers.ValidationError(_("Credenciais inválidas ou usuário não encontrado."))

        if not user.is_active:
            raise serializers.ValidationError(_("Esta conta está desativada."))

        # Exige membership ativa no tenant Bakery
        try:
            membership = TenantMembership.objects.select_related("tenant").get(
                professional=user,
                tenant=tenant,
                is_active=True,
            )
        except TenantMembership.DoesNotExist:
            raise serializers.ValidationError(_("Usuário não possui acesso a este tenant Bakery."))

        # Verifica se é customer e aplica regras de status
        customer: BakeryCustomer | None = (
            BakeryCustomer.objects
            .filter(user=user, tenant=tenant)
            .first()
        )
        if customer is not None:
            if customer.status == BakeryCustomer.ApprovalStatus.PENDING:
                raise serializers.ValidationError(_("Cadastro ainda não aprovado."))
            if customer.status == BakeryCustomer.ApprovalStatus.BLOCKED:
                raise serializers.ValidationError(_("Conta bloqueada."))

        # Gera token usando o email resolvido
        normalized_attrs = {**attrs, "email": email}
        data = super().validate(normalized_attrs)

        data["tenant_id"] = tenant.id
        data["ecosystem"] = "bakery"
        data["role"] = membership.role

        if customer is not None:
            data["customer"] = {
                "id": customer.id,
                "nickname": customer.nickname,
                "customer_type": customer.customer_type,
                "phone": customer.phone,
                "status": customer.status,
                "credit_limit": str(customer.credit_limit),
            }
        else:
            data["professional"] = {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
            }

        return data

