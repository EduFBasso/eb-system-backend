from rest_framework import serializers

from apps.legal.models import LegalClient


class LegalClientSerializer(serializers.ModelSerializer):
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
