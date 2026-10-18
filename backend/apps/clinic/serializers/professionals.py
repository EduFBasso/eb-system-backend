from typing import Any

from rest_framework import serializers

from apps.clinic.models import ClinicProfessionalProfile, ClinicProfessionalSettings


class ClinicProfessionalProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicProfessionalProfile
        fields = (
            "id",
            "system_user",
            "tenant",
            "register_number",
            "specialty",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("system_user", "tenant", "created_at", "updated_at")

    def validate_register_number(self, value):
        return (value or "").strip() or None

    def validate_specialty(self, value):
        return (value or "").strip()


class ClinicProfessionalSettingsSerializer(serializers.ModelSerializer):
    def validate_work_start_hour(self, value: int) -> int:
        if not 0 <= value <= 23:
            raise serializers.ValidationError("work_start_hour deve estar entre 0 e 23")
        return value

    def validate_work_end_hour(self, value: int) -> int:
        if not 1 <= value <= 24:
            raise serializers.ValidationError("work_end_hour deve estar entre 1 e 24")
        return value

    def validate_work_start_minute(self, value: int) -> int:
        if not 0 <= value <= 59:
            raise serializers.ValidationError("work_start_minute inválido")
        return value

    def validate_work_end_minute(self, value: int) -> int:
        if not 0 <= value <= 59:
            raise serializers.ValidationError("work_end_minute inválido")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance
        start = attrs.get("work_start_hour", getattr(instance, "work_start_hour", 6))
        start_minute = attrs.get(
            "work_start_minute", getattr(instance, "work_start_minute", 0)
        )
        end = attrs.get("work_end_hour", getattr(instance, "work_end_hour", 21))
        end_minute = attrs.get("work_end_minute", getattr(instance, "work_end_minute", 0))
        if end == 24 and end_minute != 0:
            raise serializers.ValidationError(
                {"work_end_minute": "Deve ser 0 quando work_end_hour for 24."}
            )
        if (start * 60 + start_minute) >= (end * 60 + end_minute):
            raise serializers.ValidationError(
                {"non_field_errors": "O início deve ser menor que o fim."}
            )
        return attrs

    class Meta:
        model = ClinicProfessionalSettings
        exclude = ("professional", "created_at", "updated_at")
