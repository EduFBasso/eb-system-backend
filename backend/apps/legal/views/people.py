from rest_framework.exceptions import ValidationError

from apps.legal.models import LegalClient, LegalLawyerProfile, LegalPerson
from apps.legal.serializers import (
    LegalClientSerializer,
    LegalLawyerProfileSerializer,
    LegalPersonSerializer,
)
from .base import LegalTenantViewSet


class LegalPersonViewSet(LegalTenantViewSet):
    queryset = LegalPerson.objects.all()
    serializer_class = LegalPersonSerializer

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.get_tenant())

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant())


class LegalClientViewSet(LegalTenantViewSet):
    queryset = LegalClient.objects.select_related("person", "created_by")
    serializer_class = LegalClientSerializer

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.get_tenant())

    def perform_create(self, serializer):
        person = serializer.validated_data.get("person")
        tenant = self.get_tenant()
        if person is None:
            raise ValidationError({"person": "Pessoa é obrigatória."})
        if person.tenant_id != tenant.id:
            raise ValidationError({"person": "Pessoa não pertence ao Tenant Legal ativo."})
        serializer.save(tenant=tenant, created_by=self.request.user)


class LegalLawyerProfileViewSet(LegalTenantViewSet):
    queryset = LegalLawyerProfile.objects.select_related("system_user")
    serializer_class = LegalLawyerProfileSerializer

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.get_tenant())

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.get_tenant(),
            system_user=self.request.user,
        )
