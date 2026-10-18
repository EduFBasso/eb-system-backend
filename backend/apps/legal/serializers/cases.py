from rest_framework import serializers

from apps.authentication.services.permissions import get_active_tenant_from_request
from apps.legal.models import LegalCase, LegalCaseParty, LegalRepresentation


def _active_legal_tenant(serializer):
    request = serializer.context.get("request")
    return (
        get_active_tenant_from_request(request, ecosystem="legal")
        if request
        else None
    )


class LegalCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalCase
        fields = (
            "id",
            "tenant",
            "client",
            "created_by",
            "title",
            "case_number",
            "court",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "created_by", "created_at", "updated_at")

    def validate_client(self, client):
        tenant = _active_legal_tenant(self)
        if tenant and client and client.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "Cliente não pertence ao Tenant Legal ativo."
            )
        return client


class LegalCasePartySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalCaseParty
        fields = (
            "id",
            "case",
            "person",
            "role",
            "notes",
            "is_active",
            "created_at",
        )
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = _active_legal_tenant(self)
        case = attrs.get("case", getattr(self.instance, "case", None))
        person = attrs.get("person", getattr(self.instance, "person", None))
        if tenant and case and case.tenant_id != tenant.id:
            raise serializers.ValidationError(
                {"case": "Processo não pertence ao Tenant Legal ativo."}
            )
        if tenant and person and person.tenant_id != tenant.id:
            raise serializers.ValidationError(
                {"person": "Pessoa não pertence ao Tenant Legal ativo."}
            )
        return attrs


class LegalRepresentationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalRepresentation
        fields = (
            "id",
            "party",
            "lawyer",
            "representation_type",
            "is_active",
            "created_at",
        )
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = _active_legal_tenant(self)
        party = attrs.get("party", getattr(self.instance, "party", None))
        lawyer = attrs.get("lawyer", getattr(self.instance, "lawyer", None))
        if tenant and party and party.case.tenant_id != tenant.id:
            raise serializers.ValidationError(
                {"party": "Parte não pertence ao Tenant Legal ativo."}
            )
        if tenant and lawyer and lawyer.tenant_id != tenant.id:
            raise serializers.ValidationError(
                {"lawyer": "Advogado não pertence ao Tenant Legal ativo."}
            )
        return attrs
