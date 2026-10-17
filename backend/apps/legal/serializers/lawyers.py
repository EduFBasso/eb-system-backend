from rest_framework import serializers

from apps.legal.models import LegalLawyerProfile


class LegalLawyerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalLawyerProfile
        fields = (
            "id",
            "tenant",
            "system_user",
            "oab_number",
            "oab_state",
            "official_name",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "system_user", "created_at", "updated_at")
