# backend\apps\register\serializers_auth.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _

from apps.authentication.models import TenantMembership


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)

        if user is None:
            raise serializers.ValidationError(_("Credenciais inválidas ou profissional não encontrado."))

        if not user.is_active:
            raise serializers.ValidationError(_("Essa conta está desativada."))

        # Exige membership ativa em tenant Clinic
        membership = (
            TenantMembership.objects
            .select_related("tenant")
            .filter(
                professional=user,
                is_active=True,
                tenant__is_active=True,
                tenant__ecosystem="clinic",
            )
            .first()
        )
        if membership is None:
            raise serializers.ValidationError(_("Usuário não possui acesso ao sistema Clinic."))

        data = super().validate(attrs)

        data['professional'] = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'register_number': user.register_number,
            'specialty': user.specialty,
        }
        data['tenant_id'] = membership.tenant.id
        data['ecosystem'] = 'clinic'
        data['role'] = membership.role
        data['capabilities'] = membership.tenant.capabilities

        return data

