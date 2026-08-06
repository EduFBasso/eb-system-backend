from rest_framework import serializers

from apps.bakery.models import BakeryCustomer


class BakeryCustomerSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(source="id", read_only=True)
    cnpj_cpf = serializers.CharField(read_only=True)
    is_approved = serializers.BooleanField(read_only=True)
    financial_limit = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    financial_used = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    financial_available = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    current_balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    available_credit = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = BakeryCustomer
        fields = (
            "id",
            "customer_id",
            "tenant",
            "user",
            "status",
            "customer_type",
            "nickname",
            "company_name",
            "cpf",
            "cnpj",
            "cnpj_cpf",
            "phone",
            "zip_code",
            "street",
            "number",
            "complement",
            "neighborhood",
            "city",
            "state",
            "credit_limit",
            "financial_limit",
            "financial_used",
            "financial_available",
            "current_balance",
            "available_credit",
            "is_approved",
            "approved_at",
            "approved_by",
            "blocked_at",
            "blocked_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "tenant",
            "approved_at",
            "approved_by",
            "blocked_at",
            "blocked_by",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "user": {"required": False},
        }

    def validate(self, attrs):
        customer_type = attrs.get(
            "customer_type",
            getattr(self.instance, "customer_type", BakeryCustomer.CustomerType.COMPANY),
        )
        cpf = attrs.get("cpf", getattr(self.instance, "cpf", ""))
        cnpj = attrs.get("cnpj", getattr(self.instance, "cnpj", ""))

        if customer_type == BakeryCustomer.CustomerType.INDIVIDUAL and not cpf:
            raise serializers.ValidationError({"cpf": "CPF is required for an individual."})
        if customer_type == BakeryCustomer.CustomerType.COMPANY and not cnpj:
            raise serializers.ValidationError({"cnpj": "CNPJ is required for a company."})
        return attrs