from django.db import models
from django.conf import settings


class Supplier(models.Model):
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suppliers",
        verbose_name="Profissional",
    )
    name = models.CharField("Nome", max_length=120)
    cnpj_cpf = models.CharField("CNPJ/CPF", max_length=20, blank=True)
    email = models.EmailField("E-mail", blank=True)
    phone = models.CharField("Telefone", max_length=32, blank=True)
    address = models.CharField("Endereço", max_length=255, blank=True)
    city = models.CharField("Cidade", max_length=100, blank=True)
    state = models.CharField("UF", max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("professional", "name")
        indexes = [models.Index(fields=["professional", "name"])]
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"

    def __str__(self):
        return f"{self.name}"


class ProductType(models.TextChoices):
    MEDICATION = "MEDICATION", "Medicamento"
    PRODUCT = "PRODUCT", "Produto"


class Product(models.Model):
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Profissional",
    )
    type = models.CharField(
        "Tipo", max_length=16, choices=ProductType.choices, default=ProductType.PRODUCT
    )
    name = models.CharField("Nome", max_length=160)
    scientific_name = models.CharField("Nome clínico/laboratorial", max_length=160, blank=True)
    sku = models.CharField("Código/SKU", max_length=64, blank=True)
    unit = models.CharField("Unidade", max_length=16, default="un")
    cost = models.DecimalField("Custo", max_digits=10, decimal_places=2, default=0)
    price = models.DecimalField("Preço", max_digits=10, decimal_places=2, default=0)
    track_inventory = models.BooleanField("Controla estoque", default=True)
    quantity_on_hand = models.DecimalField("Qtd em estoque", max_digits=12, decimal_places=3, default=0)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    is_active = models.BooleanField("Ativo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("professional", "name")
        indexes = [
            models.Index(fields=["professional", "type", "name"]),
            models.Index(fields=["professional", "is_active"]),
        ]
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return self.name


class StockMoveType(models.TextChoices):
    IN = "IN", "Entrada"
    OUT = "OUT", "Saída"
    ADJUST = "ADJUST", "Ajuste"


class StockMove(models.Model):
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stock_moves",
        verbose_name="Profissional",
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="moves")
    move_type = models.CharField("Tipo", max_length=8, choices=StockMoveType.choices)
    quantity = models.DecimalField("Quantidade", max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField("Custo unitário", max_digits=10, decimal_places=2, default=0)
    reason = models.CharField("Motivo", max_length=32, blank=True)
    reference = models.CharField("Referência", max_length=64, blank=True)
    notes = models.CharField("Observações", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["professional", "product", "move_type", "created_at"])]
        verbose_name = "Movimento de Estoque"
        verbose_name_plural = "Movimentos de Estoque"

    def __str__(self):
        return f"{self.get_move_type_display()} {self.quantity} {self.product.name}"


class Service(models.Model):
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="Profissional",
    )
    name = models.CharField("Serviço", max_length=160)
    description = models.TextField("Descrição", blank=True)
    base_price = models.DecimalField("Preço base", max_digits=10, decimal_places=2, default=0)
    duration_minutes = models.PositiveIntegerField("Duração (min)", default=30)
    is_active = models.BooleanField("Ativo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("professional", "name")
        indexes = [models.Index(fields=["professional", "is_active", "name"])]
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"

    def __str__(self):
        return self.name


class ServiceMaterial(models.Model):
    """Bill of Materials: materiais/insumos consumidos por serviço.

    Usado para baixar estoque automaticamente durante a execução ou finalização.
    """

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="materials")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="service_usages")
    quantity_required = models.DecimalField("Qtd por serviço", max_digits=12, decimal_places=3, default=1)

    class Meta:
        unique_together = ("service", "product")
        indexes = [models.Index(fields=["service", "product"])]
        verbose_name = "Material de Serviço"
        verbose_name_plural = "Materiais de Serviço"

    def __str__(self):
        return f"{self.service.name} — {self.quantity_required} x {self.product.name}"
