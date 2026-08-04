from rest_framework import serializers
from .models import Supplier, Product, StockMove, Service, ServiceMaterial


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "professional")

    def validate_name(self, value):
        """Valida se já existe fornecedor com este nome para o profissional."""
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return value

        professional = request.user
        # Se é atualização, exclui o próprio fornecedor da verificação
        if self.instance:
            exists = Supplier.objects.filter(
                professional=professional,
                name__iexact=value
            ).exclude(id=self.instance.id).exists()
        else:
            exists = Supplier.objects.filter(
                professional=professional,
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
        read_only_fields = ("id", "created_at", "updated_at", "professional")

    def validate_name(self, value):
        """Valida se já existe produto com este nome para o profissional."""
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return value

        professional = request.user
        # Se é atualização, exclui o próprio produto da verificação
        if self.instance:
            exists = Product.objects.filter(
                professional=professional,
                name__iexact=value
            ).exclude(id=self.instance.id).exists()
        else:
            exists = Product.objects.filter(
                professional=professional,
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
        read_only_fields = ("id", "created_at", "professional")


class ServiceMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceMaterial
        fields = "__all__"


class ServiceSerializer(serializers.ModelSerializer):
    materials = ServiceMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "professional")

    def validate_name(self, value):
        """Valida se já existe serviço com este nome para o profissional."""
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return value

        professional = request.user
        # Se é atualização, exclui o próprio serviço da verificação
        if self.instance:
            exists = Service.objects.filter(
                professional=professional,
                name__iexact=value
            ).exclude(id=self.instance.id).exists()
        else:
            exists = Service.objects.filter(
                professional=professional,
                name__iexact=value
            ).exists()

        if exists:
            raise serializers.ValidationError(
                f"Já existe um serviço com o nome '{value}' cadastrado."
            )
        return value
