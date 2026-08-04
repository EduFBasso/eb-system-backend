from typing import Any

from rest_framework import permissions

from .models import TenantMembership


def user_has_tenant_capability(user: Any, capability_name: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    memberships = TenantMembership.objects.select_related('tenant').filter(
        professional=user,
        is_active=True,
        tenant__is_active=True,
    )
    return any(
        membership.tenant.has_capability(capability_name)
        for membership in memberships
    )


def HasTenantCapability(capability_name: str):
    class TenantCapabilityPermission(permissions.BasePermission):
        def has_permission(self, request, view) -> bool:  # type: ignore[override]
            return user_has_tenant_capability(request.user, capability_name)

    TenantCapabilityPermission.__name__ = f'HasTenantCapability_{capability_name}'
    return TenantCapabilityPermission
