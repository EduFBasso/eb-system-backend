from rest_framework.exceptions import PermissionDenied

from apps.authentication.services.permissions import get_active_tenant_from_request


class BakeryTenantScopedMixin:
    """Centraliza a resolucao e injecao do tenant do ecossistema Bakery."""

    capability_name = "bakery"

    def get_active_tenant(self):
        tenant = getattr(self, "active_tenant", None)
        if tenant is None:
            tenant = get_active_tenant_from_request(
                self.request,
                ecosystem=self.capability_name,
            )
        if tenant is None:
            raise PermissionDenied("No active Bakery tenant is available.")
        return tenant

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self.get_active_tenant()
        return context