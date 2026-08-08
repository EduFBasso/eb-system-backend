from __future__ import annotations

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.authentication.models import TenantMembership
from apps.bakery.models import BakeryCustomer


class BakeryTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer de login exclusivo do ecossistema Bakery.

    Regra de acesso:
    - autentica com email + password no user global;
    - exige membership ativa em tenant ativo com capability `bakery`.
    """

    username_field = "email"

    @staticmethod
    def _resolve_customer_by_login(login_value: str) -> BakeryCustomer | None:
        # Compatibilidade com fluxo legado do frontend Bakery: login por apelido.
        return (
            BakeryCustomer.objects.select_related('user', 'tenant')
            .filter(
                nickname__iexact=login_value,
                tenant__is_active=True,
            )
            .order_by('id')
            .first()
        )

    def validate(self, attrs):
        login_value = (attrs.get("email") or "").strip()
        password = attrs.get("password")

        customer = None
        email = login_value
        if "@" not in login_value:
            customer = self._resolve_customer_by_login(login_value)
            if customer is not None:
                email = customer.user.email

        normalized_attrs = {**attrs, "email": email}

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

        if customer is None:
            customer = (
                BakeryCustomer.objects.select_related('tenant')
                .filter(user=user, tenant__is_active=True)
                .order_by('id')
                .first()
            )

        if customer is not None:
            if customer.status == BakeryCustomer.ApprovalStatus.PENDING:
                raise serializers.ValidationError(
                    _("Customer is pending approval.")
                )
            if customer.status == BakeryCustomer.ApprovalStatus.BLOCKED:
                raise serializers.ValidationError(
                    _("Customer is blocked.")
                )

        data = super().validate(normalized_attrs)
        if customer is not None:
            data["customer"] = {
                "id": customer.id,
                "customer_id": customer.id,
                "nickname": customer.nickname,
                "customer_type": customer.customer_type,
                "phone": customer.phone,
                "status": customer.status,
                "zip_code": customer.zip_code,
                "street": customer.street,
                "number": customer.number,
                "complement": customer.complement,
                "neighborhood": customer.neighborhood,
                "city": customer.city,
                "state": customer.state,
                "credit_limit": str(customer.credit_limit),
            }
        else:
            data["professional"] = {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
            }
        data["ecosystem"] = "bakery"
        return data
