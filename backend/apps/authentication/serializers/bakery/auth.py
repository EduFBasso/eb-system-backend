from __future__ import annotations

from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings

from apps.authentication.models import TenantMembership
from apps.authentication.services.bakery_auth import (
    BakeryLoginContext,
    authenticate_bakery_user,
    build_customer_snapshot,
    build_professional_snapshot,
    build_tenant_snapshot,
)
from apps.authentication.services.device_sessions import (
    activate_login_session,
    resolve_device_id,
)
from apps.bakery.models import BakeryCustomer


class BakeryLoginSerializer(TokenObtainPairSerializer):
    """Base do login Bakery. Cada perfil define apenas suas regras e payload.

    Recebe: { login, password, tenant_slug }
    - login pode ser email ou login_alias da membership naquele tenant.
    - tenant_slug identifica o tenant sem ambiguidade.
    """

    username_field = "email"

    login = serializers.CharField(write_only=True)
    tenant_slug = serializers.SlugField(write_only=True)
    device_id = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=64,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("email", None)

    def validate_profile(self, context: BakeryLoginContext) -> None:
        raise NotImplementedError

    def profile_payload(self, context: BakeryLoginContext) -> dict:
        raise NotImplementedError

    def get_token(self, user):
        token = super().get_token(user)
        tenant = getattr(self, "_login_tenant", None)
        membership = getattr(self, "_login_membership", None)
        device_id = getattr(self, "_login_device_id", None)
        if tenant is not None and membership is not None:
            token["tenant_id"] = tenant.id
            token["ecosystem"] = "bakery"
            token["role"] = membership.role
        if device_id:
            token["device_id"] = device_id
        return token

    def validate(self, attrs):
        request = self.context.get("request")
        context = authenticate_bakery_user(
            login=attrs.get("login", ""),
            password=attrs.get("password", ""),
            tenant_slug=attrs.get("tenant_slug", ""),
            request=request,
        )
        # As regras de perfil rodam antes de criar a sessão de dispositivo.
        self.validate_profile(context)

        user = context.user
        device_id = resolve_device_id(attrs.get("device_id", ""), user)
        user_agent = ""
        ip_address = None
        if request is not None:
            user_agent = (request.META.get("HTTP_USER_AGENT", "") or "")[:255]
            ip_address = request.META.get("REMOTE_ADDR")
        active_count = activate_login_session(
            user,
            device_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        self._login_tenant = context.tenant
        self._login_membership = context.membership
        self._login_device_id = device_id
        self.user = user
        refresh = self.get_token(user)

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "tenant_id": context.tenant.id,
            "ecosystem": "bakery",
            "role": context.membership.role,
            "device_id": device_id,
            "active_sessions_count": active_count,
            "tenant": build_tenant_snapshot(context.tenant),
            **self.profile_payload(context),
        }


class BakeryAdminLoginSerializer(BakeryLoginSerializer):
    """Login administrativo: somente owner/admin ativos do tenant."""

    ALLOWED_ROLES = (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)

    def validate_profile(self, context: BakeryLoginContext) -> None:
        if context.membership.role not in self.ALLOWED_ROLES:
            raise serializers.ValidationError(
                _("Esta conta não possui acesso administrativo. Use o login de cliente.")
            )

    def profile_payload(self, context: BakeryLoginContext) -> dict:
        return {"professional": build_professional_snapshot(context.user)}


class BakeryCustomerLoginSerializer(BakeryLoginSerializer):
    """Login de cliente: somente member com BakeryCustomer aprovado no tenant."""

    def validate_profile(self, context: BakeryLoginContext) -> None:
        if context.membership.role != TenantMembership.Role.MEMBER:
            raise serializers.ValidationError(
                _("Conta administrativa não pode entrar como cliente. Use o login administrativo.")
            )

        customer = context.customer
        if customer is None:
            raise serializers.ValidationError(_("Cadastro de cliente não encontrado neste tenant."))
        if customer.status == BakeryCustomer.ApprovalStatus.PENDING:
            raise serializers.ValidationError(_("Cadastro ainda não aprovado."))
        if customer.status == BakeryCustomer.ApprovalStatus.BLOCKED:
            raise serializers.ValidationError(_("Conta bloqueada."))
        if customer.status != BakeryCustomer.ApprovalStatus.APPROVED:
            raise serializers.ValidationError(_("Cadastro de cliente não está ativo."))

    def profile_payload(self, context: BakeryLoginContext) -> dict:
        return {"customer": build_customer_snapshot(context.customer)}
