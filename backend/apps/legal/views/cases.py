from rest_framework.exceptions import ValidationError

from apps.legal.models import (
    LegalCase,
    LegalCaseParty,
    LegalRepresentation,
)
from apps.legal.serializers import (
    LegalCasePartySerializer,
    LegalCaseSerializer,
    LegalRepresentationSerializer,
)
from .base import LegalTenantViewSet


class LegalCaseViewSet(LegalTenantViewSet):
    queryset = LegalCase.objects.select_related("client", "created_by")
    serializer_class = LegalCaseSerializer

    def perform_create(self, serializer):
        tenant = self.get_tenant()
        client = serializer.validated_data.get("client")
        if client and client.tenant_id != tenant.id:
            raise ValidationError({"client": "Cliente não pertence ao Tenant Legal ativo."})
        serializer.save(tenant=tenant, created_by=self.request.user)


class LegalCasePartyViewSet(LegalTenantViewSet):
    queryset = LegalCaseParty.objects.select_related("case", "person")
    serializer_class = LegalCasePartySerializer

    def get_queryset(self):
        return super().get_queryset().filter(case__tenant=self.get_tenant())

    def perform_create(self, serializer):
        tenant = self.get_tenant()
        case = serializer.validated_data["case"]
        person = serializer.validated_data["person"]
        if case.tenant_id != tenant.id:
            raise ValidationError({"case": "Processo não pertence ao Tenant Legal ativo."})
        if person.tenant_id != tenant.id:
            raise ValidationError({"person": "Pessoa não pertence ao Tenant Legal ativo."})
        serializer.save()


class LegalRepresentationViewSet(LegalTenantViewSet):
    queryset = LegalRepresentation.objects.select_related(
        "party__case",
        "party__person",
        "lawyer__system_user",
    )
    serializer_class = LegalRepresentationSerializer

    def get_queryset(self):
        return super().get_queryset().filter(party__case__tenant=self.get_tenant())

    def perform_create(self, serializer):
        tenant = self.get_tenant()
        party = serializer.validated_data["party"]
        lawyer = serializer.validated_data["lawyer"]
        if party.case.tenant_id != tenant.id:
            raise ValidationError({"party": "Parte não pertence ao Tenant Legal ativo."})
        if lawyer.tenant_id != tenant.id:
            raise ValidationError({"lawyer": "Advogado não pertence ao Tenant Legal ativo."})
        serializer.save()
