from __future__ import annotations

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.authentication.models import TenantMembership


class BakeryTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer de login exclusivo do ecossistema Bakery.

    Regra de acesso:
    - autentica com email + password no user global;
    - exige membership ativa em tenant ativo com capability `bakery`.
    """

    username_field = "email"

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)
        if user is None:
            raise serializers.ValidationError(
                _("Invalid credentials or user not found.")
            )

        if not user.is_active:
            raise serializers.ValidationError(_("This account is inactive."))

        memberships = TenantMembership.objects.select_related("tenant").filter(
            professional=user,
            is_active=True,
            tenant__is_active=True,
        )
        has_bakery_capability = any(
            membership.tenant.has_capability("bakery")
            for membership in memberships
        )
        if not has_bakery_capability:
            raise serializers.ValidationError(
                _("User has no active tenant with bakery capability.")
            )

        data = super().validate(attrs)
        data["professional"] = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        }
        data["ecosystem"] = "bakery"
        return data
