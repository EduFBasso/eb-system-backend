from rest_framework import serializers
from rest_framework.permissions import BasePermission

from apps.authentication.models import SystemUser


class ClinicProfessionalSerializer(serializers.ModelSerializer):
    def validate_register_number(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    def validate_specialty(self, value: str) -> str:
        return (value or "").strip()

    def validate_state(self, value: str) -> str:
        return (value or "").strip().upper()

    class Meta:
        model = SystemUser
        fields = [
            "id", "email", "first_name", "last_name", "display_name",
            "register_number", "specialty", "phone", "city", "state",
            "address", "number", "neighborhood", "zip_code", "cnpj",
            "can_manage_professionals", "is_active", "is_staff", "is_superuser",
            "created_at", "deactivated_at", "deactivation_reason", "ui_theme",
            "lock_odonto_plan_after_print", "odonto_quote_validity_days",
        ]
        extra_kwargs = {"can_manage_professionals": {"required": False}}


class CanManageClinicProfessionals(BasePermission):
    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        return request.user.is_authenticated and bool(
            getattr(request.user, "can_manage_professionals", False)
        )


# Compatibility aliases for current Clinic views and external imports.
ProfessionalSerializer = ClinicProfessionalSerializer
CanManageProfessionals = CanManageClinicProfessionals
