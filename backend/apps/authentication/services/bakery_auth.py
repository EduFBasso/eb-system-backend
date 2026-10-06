from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.authentication.services.login_identity import resolve_login_email
from apps.bakery.models import BakeryCustomer


@dataclass(frozen=True)
class BakeryLoginContext:
    user: Professional
    tenant: Tenant
    membership: TenantMembership
    customer: BakeryCustomer | None


def authenticate_bakery_user(
    *,
    login: str,
    password: str,
    tenant_slug: str,
    request=None,
) -> BakeryLoginContext:
    """Valida tenant, credenciais e membership ativa, sem regras de perfil."""
    login = (login or "").strip()
    tenant_slug = (tenant_slug or "").strip()
    if not login or not password or not tenant_slug:
        raise serializers.ValidationError(_("login, password e tenant_slug são obrigatórios."))

    try:
        tenant = Tenant.objects.get(
            slug=tenant_slug,
            is_active=True,
            ecosystem=Tenant.Ecosystem.BAKERY,
        )
    except Tenant.DoesNotExist:
        raise serializers.ValidationError(_("Tenant Bakery não encontrado ou inativo."))

    email = resolve_login_email(login, tenant)
    if not email:
        raise serializers.ValidationError(_("Credenciais inválidas ou usuário não encontrado."))

    user = authenticate(username=email, password=password, request=request)
    if user is None:
        raise serializers.ValidationError(_("Credenciais inválidas ou usuário não encontrado."))

    if not user.is_active:
        raise serializers.ValidationError(_("Esta conta está desativada."))

    try:
        membership = TenantMembership.objects.get(
            professional=user,
            tenant=tenant,
            is_active=True,
        )
    except TenantMembership.DoesNotExist:
        raise serializers.ValidationError(_("Usuário não possui acesso a este tenant Bakery."))

    customer = BakeryCustomer.objects.filter(user=user, tenant=tenant).first()
    return BakeryLoginContext(user=user, tenant=tenant, membership=membership, customer=customer)


def build_tenant_snapshot(tenant: Tenant) -> dict:
    return {
        "slug": tenant.slug,
        "trade_name": tenant.trade_name,
        "address": {
            "zip_code": tenant.zip_code,
            "street": tenant.street,
            "number": tenant.number,
            "neighborhood": tenant.neighborhood,
            "city": tenant.city,
            "state": tenant.state,
            "complement": tenant.complement,
        },
    }


def build_professional_snapshot(user: Professional) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": str(user.phone) if user.phone else "",
    }


def build_customer_snapshot(customer: BakeryCustomer) -> dict:
    return {
        "id": customer.id,
        "nickname": customer.nickname,
        "customer_type": customer.customer_type,
        "phone": customer.phone,
        "status": customer.status,
        "credit_limit": str(customer.credit_limit),
    }
