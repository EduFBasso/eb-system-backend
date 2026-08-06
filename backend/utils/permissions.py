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


class HasActiveBakeryTenant(permissions.BasePermission):
    """Exige autenticacao e tenant ativo com capability Bakery."""

    message = "User has no active tenant with bakery capability."

    def has_permission(self, request, view) -> bool:
        tenant = get_active_tenant(request.user, "bakery")
        if tenant is None:
            return False
        view.active_tenant = tenant
        return True


class IsCustomerOrAdmin(permissions.BasePermission):
    """Permite acesso ao cliente autenticado ou a um usuario staff."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if getattr(request.user, "is_staff", False):
            return True
        owner = getattr(obj, "user", None)
        if owner is None and hasattr(obj, "customer"):
            owner = obj.customer.user
        return owner == request.user


class IsRelatedCustomer(permissions.BasePermission):
    """Restringe pedidos e lancamentos ao cliente relacionado."""

    def has_object_permission(self, request, view, obj) -> bool:
        if getattr(request.user, "is_staff", False):
            return True
        customer = getattr(obj, "customer", None)
        if customer is None:
            order = getattr(obj, "order", None)
            customer = getattr(order, "customer", None)
        return bool(customer and customer.user_id == request.user.id)


class IsTenantStaffOrReadOnly(permissions.BasePermission):
    """Permite leitura autenticada e mutacoes somente para staff."""

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user.is_staff)
