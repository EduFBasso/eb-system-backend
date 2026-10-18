from rest_framework import serializers

from apps.legal.models import LegalPerson


class LegalPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalPerson
        fields = (
            "id",
            "tenant",
            "person_type",
            "name",
            "document",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "created_at", "updated_at")
