from rest_framework import serializers

from apps.authentication.models import Tenant


class BakeryTenantProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = (
            "name",
            "trade_name",
            "slug",
            "ecosystem",
            "zip_code",
            "street",
            "number",
            "neighborhood",
            "city",
            "state",
            "complement",
        )
        read_only_fields = ("name", "slug", "ecosystem")

    def validate_state(self, value: str) -> str:
        return value.strip().upper()

    def validate(self, attrs):
        tenant = self.instance
        if tenant and tenant.ecosystem != Tenant.Ecosystem.BAKERY:
            raise serializers.ValidationError("O tenant informado não pertence ao Bakery.")
        return attrs