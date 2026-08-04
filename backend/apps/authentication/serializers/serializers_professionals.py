from rest_framework import serializers
from .models import Professional
from rest_framework.permissions import BasePermission

class ProfessionalSerializer(serializers.ModelSerializer):
    def validate_register_number(self, value):
        # Campo e unico no banco; string vazia duplicada gera IntegrityError.
        # Normalizamos vazio para None para manter comportamento seguro.
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    def validate_specialty(self, value: str) -> str:
        return (value or '').strip()

    def validate_state(self, value: str) -> str:
        return (value or '').strip().upper()

    class Meta:
        model = Professional
        fields = [
            'id', 'email', 'first_name', 'last_name', 'display_name', 'register_number',
            'specialty', 'phone', 'city', 'state',
            'can_manage_professionals', 'is_active', 'is_staff', 'is_superuser',
            'created_at', 'deactivated_at', 'deactivation_reason',
            'ui_theme',
        ]
        extra_kwargs = {
            'can_manage_professionals': {'required': False},
        }


class ProfessionalBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Professional
        fields = ['id', 'email', 'first_name', 'last_name', 'display_name', 'register_number']


class CanManageProfessionals(BasePermission):
    def has_permission(self, request, view) -> bool: # type: ignore[override]
        return request.user.is_authenticated and bool(getattr(request.user, 'can_manage_professionals', False))
    
      
