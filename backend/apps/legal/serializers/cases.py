from rest_framework import serializers

from apps.legal.models import LegalCase, LegalCaseParty, LegalRepresentation


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
