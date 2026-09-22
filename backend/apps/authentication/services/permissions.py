from typing import Any

from rest_framework import permissions

from apps.authentication.models import TenantMembership


def get_active_tenant_membership(user: Any, *, ecosystem: str | None = None):
    """Fallback sem contexto de requisição para scripts e testes diretos."""
    if not user or not user.is_authenticated:
        return None

    memberships = TenantMembership.objects.select_related('tenant').filter(
        professional=user,
        is_active=True,
        tenant__is_active=True,
    )
    if ecosystem is not None:
        memberships = memberships.filter(tenant__ecosystem=ecosystem)
    return memberships.order_by('created_at', 'id').first()


def get_tenant_membership_from_request(
    request: Any,
    *,
    ecosystem: str | None = None,
):
    """Resolve o tenant escolhido no login, sem reabrir a seleção por ordem."""
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    memberships = TenantMembership.objects.select_related('tenant').filter(
        professional=user,
        is_active=True,
        tenant__is_active=True,
    )
    if ecosystem is not None:
        memberships = memberships.filter(tenant__ecosystem=ecosystem)

    auth_token = getattr(request, 'auth', None)
    tenant_id = auth_token.get('tenant_id') if auth_token is not None else None
    if tenant_id is not None:
        return memberships.filter(tenant_id=tenant_id).first()

    return memberships.order_by('created_at', 'id').first()


def user_has_tenant_capability(
    user: Any,
    capability_name: str,
    *,
    ecosystem: str | None = None,
) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    membership = get_active_tenant_membership(user, ecosystem=ecosystem)
    return bool(
        membership and membership.tenant.has_capability(capability_name)
    )


def HasTenantCapability(capability_name: str, *, ecosystem: str | None = None):
    class TenantCapabilityPermission(permissions.BasePermission):
        def has_permission(self, request, view) -> bool:  # type: ignore[override]
            if getattr(request.user, 'is_superuser', False):
                return True
            membership = get_tenant_membership_from_request(
                request,
                ecosystem=ecosystem,
            )
            return bool(
                membership and membership.tenant.has_capability(capability_name)
            )

    TenantCapabilityPermission.__name__ = f'HasTenantCapability_{capability_name}'
    return TenantCapabilityPermission
