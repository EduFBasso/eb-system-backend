# backend\apps\register\serializers_auth.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    # Garantimos que o campo de entrada é 'email' + 'password'
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)

        if user is None:
            raise serializers.ValidationError(_("Credenciais inválidas ou profissional não encontrado."))

        if not user.is_active:
            raise serializers.ValidationError(_("Essa conta está desativada."))

        data = super().validate(attrs)

        # Adiciona dados extras ao payload do frontend
        data['professional'] = {  # type: ignore[assignment]
            'id': user.id,  # type: ignore[union-attr]
            'first_name': user.first_name,  # type: ignore[union-attr]
            'last_name': user.last_name,  # type: ignore[union-attr]
            'email': user.email,  # type: ignore[union-attr]
            'register_number': user.register_number,  # type: ignore[union-attr]
            'specialty': user.specialty  # type: ignore[union-attr]
        }

        return data
    
