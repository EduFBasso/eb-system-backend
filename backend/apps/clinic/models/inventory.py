from django.db import models


class Supplier(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela o cadastro de Fornecedores parceiros homologados pela clínica.
    O fornecedor pertence ao Tenant (Clínica), permitindo compras centralizadas.
    """
    # [Multi-tenant] O fornecedor é patrimônio da clínica
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        related_name="suppliers",
        verbose_name="Clínica/Tenant",
        null=False,
        blank=False,
    )
    name = models.CharField("Nome / Razão Social", max_length=120)
    cnpj_cpf = models.CharField("CNPJ/CPF", max_length=20, blank=True)
    email = models.EmailField("E-mail de Contato", blank=True)
    phone = models.CharField("Telefone / WhatsApp", max_length=32, blank=True)
    address = models.CharField("Endereço Comercial", max_length=255, blank=True)
    city = models.CharField("Cidade", max_length=100, blank=True)
    state = models.CharField("UF (Estado)", max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        # Garante que não haja fornecedores duplicados com o mesmo nome na mesma clínica
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='uniq_supplier_tenant_name'
            )
        ]
        indexes = [models.Index(fields=["tenant", "name"])]
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"

    def __str__(self):
        return self.name


class ProductType(models.TextChoices):
    MEDICATION = "MEDICATION", "Medicamento / Insumo Clínico"
    PRODUCT = "PRODUCT", "Produto de Venda / Prateleira"


class Product(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Gerencia o cadastro do catálogo de mercadorias e insumos da clínica.
    Controla custos, preços de venda e quantidades vigentes em estoque.
    """
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Clínica/Tenant",
        null=False,
        blank=False,
    )
    type = models.CharField(
        "Tipo de Item", max_length=16, choices=ProductType.choices, default=ProductType.PRODUCT
    )
    name = models.CharField("Nome do Produto", max_length=160)
    scientific_name = models.CharField("Nome Clínico / Princípio Ativo", max_length=160, blank=True)
    sku = models.CharField("Código interno / SKU", max_length=64, blank=True)
    unit = models.CharField("Unidade de Medida (un, cx, ml)", max_length=16, default="un")
    cost = models.DecimalField("Preço de Custo (R$)", max_digits=10, decimal_places=2, default=0)
    price = models.DecimalField("Preço de Venda (R$)", max_digits=10, decimal_places=2, default=0)
    track_inventory = models.BooleanField("Ativar controle de estoque?", default=True)
    quantity_on_hand = models.DecimalField("Quantidade Atual em Estoque", max_digits=12, decimal_places=3, default=0)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="products", verbose_name="Fornecedor Padrão"
    )
    is_active = models.BooleanField("Produto Ativo?", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='uniq_product_tenant_name'
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "type", "name"]),
            models.Index(fields=["tenant", "is_active"]),
        ]
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return self.name


class StockMoveType(models.TextChoices):
    IN = "IN", "Entrada (Compra/Reposição)"
    OUT = "OUT", "Saída (Consumo/Venda)"
    ADJUST = "ADJUST", "Ajuste Inventário (Quebra/Balanço)"


class StockMove(models.Model):
    """
    [SOLID - Single Responsibility]
    Registra a auditoria cronológica e imutável de movimentações de estoque.
    Qualquer alteração na quantidade do produto gera uma linha nesta tabela.
    """
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        related_name="stock_moves",
        verbose_name="Clínica/Tenant",
        null=False,
        blank=False,
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="moves", verbose_name="Produto")
    move_type = models.CharField("Tipo de Movimento", max_length=8, choices=StockMoveType.choices)
    quantity = models.DecimalField("Quantidade Movimentada", max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField("Custo Unitário no Momento (R$)", max_digits=10, decimal_places=2, default=0)
    reason = models.CharField("Motivo / Justificativa", max_length=32, blank=True)
    reference = models.CharField("Documento de Referência (ex: Nº Nota)", max_length=64, blank=True)
    notes = models.CharField("Observações Adicionais", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'clinic'
        indexes = [models.Index(fields=["tenant", "product", "move_type", "created_at"])]
        verbose_name = "Movimento de Estoque"
        verbose_name_plural = "Movimentos de Estoque"

    def __str__(self):
        return f"{self.get_move_type_display()} - {self.quantity} x {self.product.name}"


class Service(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela o catálogo unificado de procedimentos e serviços oferecidos pela clínica.
    """
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="Clínica/Tenant",
        null=False,
        blank=False,
    )
    name = models.CharField("Nome do Serviço / Procedimento", max_length=160)
    description = models.TextField("Descrição Técnica do Procedimento", blank=True)
    base_price = models.DecimalField("Preço Base Sugerido (R$)", max_digits=10, decimal_places=2, default=0)
    duration_minutes = models.PositiveIntegerField("Duração Estimada (Minutos)", default=30)
    is_active = models.BooleanField("Serviço Ativo?", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='uniq_service_tenant_name'
            )
        ]
        indexes = [models.Index(fields=["tenant", "is_active", "name"])]
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"

    def __str__(self):
        return self.name


class ServiceMaterial(models.Model):
    """
    [SOLID - Interface Segregation Principle]
    Ficha Técnica / Bill of Materials (BOM).
    Mapeia os insumos que são consumidos de forma automática do estoque da clínica
    quando o serviço é realizado (ex: 1 par de luvas para cada procedimento de Podologia).
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="materials", verbose_name="Serviço")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="service_usages", verbose_name="Insumo / Produto")
    quantity_required = models.DecimalField("Quantidade Consumida por Execução", max_digits=12, decimal_places=3, default=1)

    class Meta:
        app_label = 'clinic'
        constraints = [
            models.UniqueConstraint(
                fields=['service', 'product'],
                name='uniq_service_material_combination'
            )
        ]
        indexes = [models.Index(fields=["service", "product"])]
        verbose_name = "Material de Serviço"
        verbose_name_plural = "Materiais de Serviço"

    def __str__(self):
        return f"{self.service.name} — {self.quantity_required} x {self.product.name}"
