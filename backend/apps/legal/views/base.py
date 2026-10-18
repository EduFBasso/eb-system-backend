from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.authentication.services.permissions import (
    HasTenantCapability,
    get_active_tenant_from_request,
)


class LegalTenantViewSet(ModelViewSet):
    permission_classes = (
        IsAuthenticated,
        HasTenantCapability("legal", ecosystem="legal"),
    )

    def get_tenant(self):
        tenant = get_active_tenant_from_request(self.request, ecosystem="legal")
        if tenant is None:
            self.permission_denied(self.request, message="Tenant Legal ativo não localizado.")
        return tenant

    def get_queryset(self):
        return super().get_queryset()
