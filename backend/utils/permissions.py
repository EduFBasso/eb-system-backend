from __future__ import annotations

from typing import Any

from rest_framework import permissions

from apps.authentication.models import Tenant, TenantMembership


def get_active_tenant(user: Any, capability_name: str | None = None) -> Tenant | None:
    """Resolve deterministicamente o primeiro tenant ativo do usuario.

    Quando uma capability e informada, ignora memberships de tenants que nao
    habilitam aquele ecossistema.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return None

    memberships = (
        TenantMembership.objects.select_related("tenant")
        .filter(
            professional=user,
            is_active=True,
            tenant__is_active=True,
        )
        .order_by("created_at", "id")
    )
    for membership in memberships:
        if capability_name and not membership.tenant.has_capability(capability_name):
            continue
        return membership.tenant
    return None


def _get_bakery_membership(request) -> TenantMembership | None:
    """Retorna a membership Bakery do usuário extraindo tenant_id do token JWT."""
    tenant_id = getattr(request, "_bakery_tenant_id", None)
    if tenant_id is None:
        # Fallback: first active Bakery tenant (usado antes do JWT fixar tenant_id)
        tenant = get_active_tenant(request.user, "bakery")
        if tenant is None:
            return None
        tenant_id = tenant.id

    try:
        return (
            TenantMembership.objects
            .select_related("tenant")
            .get(
                professional=request.user,
                tenant_id=tenant_id,
                is_active=True,
                tenant__is_active=True,
            )
        )
    except TenantMembership.DoesNotExist:
        return None


class HasActiveBakeryTenant(permissions.BasePermission):
    """Exige autenticação e membership ativa em tenant Bakery."""

    message = "Usuário não possui acesso a um tenant Bakery ativo."

    def has_permission(self, request, view) -> bool:
        membership = _get_bakery_membership(request)
        if membership is None:
            return False
        view.active_tenant = membership.tenant
        view.bakery_membership = membership
        return True


class IsBakeryOwner(permissions.BasePermission):
    """Exige membership role=owner ou admin no tenant Bakery do token."""

    message = "Apenas administradores podem executar esta ação."

    def has_permission(self, request, view) -> bool:
        if getattr(request.user, "is_staff", False):
            return True
        membership = _get_bakery_membership(request)
        if membership is None:
            return False
        return membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)


class IsBakeryCustomer(permissions.BasePermission):
    """Exige membership role=member + BakeryCustomer aprovado no tenant."""

    message = "Acesso restrito ao cliente aprovado."

    def has_permission(self, request, view) -> bool:
        from apps.bakery.models import BakeryCustomer

        membership = _get_bakery_membership(request)
        if membership is None:
            return False
        if membership.role != TenantMembership.Role.MEMBER:
            return False
        return BakeryCustomer.objects.filter(
            user=request.user,
            tenant=membership.tenant,
            status=BakeryCustomer.ApprovalStatus.APPROVED,
        ).exists()


class IsCustomerOrAdmin(permissions.BasePermission):
    """Owner/Admin vê tudo; customer vê apenas o próprio perfil."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if getattr(request.user, "is_staff", False):
            return True
        membership = _get_bakery_membership(request)
        if membership and membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN):
            return True
        owner = getattr(obj, "user", None)
        if owner is None and hasattr(obj, "customer"):
            owner = obj.customer.user
        return owner == request.user


class IsRelatedCustomer(permissions.BasePermission):
    """Owner/Admin acessa tudo; customer acessa apenas seus próprios registros."""

    def has_object_permission(self, request, view, obj) -> bool:
        if getattr(request.user, "is_staff", False):
            return True
        membership = _get_bakery_membership(request)
        if membership and membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN):
            return True
        customer = getattr(obj, "customer", None)
        if customer is None:
            order = getattr(obj, "order", None)
            customer = getattr(order, "customer", None)
        return bool(customer and customer.user_id == request.user.id)


class IsTenantStaffOrReadOnly(permissions.BasePermission):
    """Owner/Admin edita; outros apenas lêem."""

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if getattr(request.user, "is_staff", False):
            return True
        membership = _get_bakery_membership(request)
        return bool(membership and membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN))

