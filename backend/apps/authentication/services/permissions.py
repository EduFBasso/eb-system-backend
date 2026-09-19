from typing import Any

from rest_framework import permissions

from apps.authentication.models import TenantMembership


def get_active_tenant_membership(user: Any, *, ecosystem: str | None = None):
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
            return user_has_tenant_capability(
                request.user,
                capability_name,
                ecosystem=ecosystem,
            )

    TenantCapabilityPermission.__name__ = f'HasTenantCapability_{capability_name}'
    return TenantCapabilityPermission
