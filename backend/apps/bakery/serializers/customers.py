from rest_framework import serializers
from django.db.models.functions import Lower, Trim

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
            "user",
            "status",
            "credit_limit",
            "approved_at",
            "approved_by",
            "blocked_at",
            "blocked_by",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "cpf": {"required": False, "allow_blank": True},
            "cnpj": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        nickname = attrs.get("nickname")
        if nickname is not None:
            nickname = nickname.strip()
            attrs["nickname"] = nickname
            if not nickname:
                raise serializers.ValidationError({"nickname": "Informe um nome ou apelido para o cliente."})

            if self.instance and self.instance.status != BakeryCustomer.ApprovalStatus.PENDING:
                current_nickname = self.instance.nickname.strip()
                if nickname.casefold() != current_nickname.casefold():
                    raise serializers.ValidationError(
                        {"nickname": "O cliente aprovado ou bloqueado não pode alterar o nome ou apelido."}
                    )

            tenant = getattr(self.instance, "tenant", None) or self.context.get("tenant")
            if tenant is not None:
                duplicate = BakeryCustomer.objects.filter(tenant=tenant).annotate(
                    normalized_nickname=Lower(Trim("nickname")),
                ).filter(normalized_nickname=nickname.lower())
                if self.instance:
                    duplicate = duplicate.exclude(pk=self.instance.pk)
                if duplicate.exists():
                    raise serializers.ValidationError(
                        {"nickname": "Esse nome ou apelido já está em uso. Escolha outro identificador."}
                    )

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