from rest_framework import serializers
from apps.clinic.models.inventory import Supplier, Product, StockMove, Service, ServiceMaterial


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "tenant")

    def validate_name(self, value):
        """Valida se já existe fornecedor com este nome para o profissional."""
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return value

        tenant = request.user.tenant_memberships.filter(
            is_active=True, tenant__is_active=True
        ).values_list("tenant_id", flat=True).first()
        if tenant is None:
            return value
        # Se é atualização, exclui o próprio fornecedor da verificação
        if self.instance:
            exists = Supplier.objects.filter(
                tenant_id=tenant,
                name__iexact=value
            ).exclude(id=self.instance.id).exists()
        else:
            exists = Supplier.objects.filter(
                tenant_id=tenant,
                name__iexact=value
            ).exists()

        if exists:
            raise serializers.ValidationError(
                f"Já existe um fornecedor com o nome '{value}' cadastrado."
            )
        return value


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "tenant")

    def validate_name(self, value):
        """Valida se já existe produto com este nome para o profissional."""
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return value

        tenant = request.user.tenant_memberships.filter(
            is_active=True, tenant__is_active=True
        ).values_list("tenant_id", flat=True).first()
        if tenant is None:
            return value
        # Se é atualização, exclui o próprio produto da verificação
        if self.instance:
            exists = Product.objects.filter(
                tenant_id=tenant,
                name__iexact=value
            ).exclude(id=self.instance.id).exists()
        else:
            exists = Product.objects.filter(
                tenant_id=tenant,
                name__iexact=value
            ).exists()

        if exists:
            raise serializers.ValidationError(
                f"Já existe um produto com o nome '{value}' cadastrado."
            )
        return value


class StockMoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMove
        fields = "__all__"
        read_only_fields = ("id", "created_at", "tenant")


class ServiceMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceMaterial
        fields = "__all__"


class ServiceSerializer(serializers.ModelSerializer):
    materials = ServiceMaterialSerializer(many=True, read_only=True)
    treatment_scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=('tooth', 'arch', 'other')),
        required=False,
    )

    class Meta:
        model = Service
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "tenant")

    def validate_name(self, value):
        """Valida se já existe serviço com este nome para o profissional."""
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return value

        tenant = request.user.tenant_memberships.filter(
            is_active=True, tenant__is_active=True
        ).values_list("tenant_id", flat=True).first()
        if tenant is None:
            return value
        # Se é atualização, exclui o próprio serviço da verificação
        if self.instance:
            exists = Service.objects.filter(
                tenant_id=tenant,
                name__iexact=value
            ).exclude(id=self.instance.id).exists()
        else:
            exists = Service.objects.filter(
                tenant_id=tenant,
                name__iexact=value
            ).exists()

        if exists:
            raise serializers.ValidationError(
                f"Já existe um serviço com o nome '{value}' cadastrado."
            )
        return value

    def validate_treatment_scopes(self, value):
        return list(dict.fromkeys(value))
