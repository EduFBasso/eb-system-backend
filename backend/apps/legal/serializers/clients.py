from rest_framework import serializers

from apps.authentication.services.permissions import get_active_tenant_from_request
from apps.legal.models import LegalClient, LegalPerson


class LegalClientSerializer(serializers.ModelSerializer):
    person = serializers.PrimaryKeyRelatedField(
        queryset=LegalPerson.objects.all(),
        required=True,
        allow_null=False,
    )
    person_name = serializers.CharField(source="person.name", read_only=True)

    class Meta:
        model = LegalClient
        fields = (
            "id",
            "tenant",
            "person",
            "person_name",
            "created_by",
            "status",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "created_by", "created_at", "updated_at")

    def validate_person(self, person):
        request = self.context.get("request")
        tenant = (
            get_active_tenant_from_request(request, ecosystem="legal")
            if request
            else None
        )
        if tenant and person.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "Pessoa não pertence ao Tenant Legal ativo."
            )
        return person
