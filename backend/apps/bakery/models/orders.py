from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from .customers import BakeryCustomer, ZERO


class Product(models.Model):
    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.PROTECT,
        related_name="bakery_products",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "bakery"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uq_bakery_product_tenant_name",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=ZERO),
                name="ck_bakery_product_price_nonnegative",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "is_active", "name"])]

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        CONFIRMED = "CONFIRMED", "Confirmado"
        DELIVERED = "DELIVERED", "Entregue"
        CANCELLED = "CANCELLED", "Cancelado"

    class PaymentMethod(models.TextChoices):
        CREDIT = "CREDIT", "Fiado"
        CASH = "CASH", "Dinheiro"
        PIX = "PIX", "PIX"
        TRANSFER = "TRANSFER", "Transferencia"

    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.PROTECT,
        related_name="bakery_orders",
    )
    customer = models.ForeignKey(
        BakeryCustomer,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    delivery_date = models.DateTimeField()
    shipping_zip_code = models.CharField(
        max_length=8,
        validators=[RegexValidator(r"^\d{8}$", "ZIP code must contain 8 digits.")],
    )
    shipping_street = models.CharField(max_length=150)
    shipping_number = models.CharField(max_length=20)
    shipping_complement = models.CharField(max_length=100, blank=True)
    shipping_neighborhood = models.CharField(max_length=100)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    paid_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "bakery"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "customer", "status"]),
            models.Index(fields=["tenant", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Order #{self.pk} - {self.customer.nickname} ({self.status})"

    def clean(self) -> None:
        if self.customer_id and self.tenant_id != self.customer.tenant_id:
            raise ValidationError({"customer": "Customer must belong to the order tenant."})

    def save(self, *args, **kwargs):
        if self.customer_id and not self.shipping_zip_code:
            # O endereco e copiado para preservar o snapshot historico da entrega.
            self.shipping_zip_code = self.customer.zip_code
            self.shipping_street = self.customer.street
            self.shipping_number = self.customer.number
            self.shipping_complement = self.customer.complement
            self.shipping_neighborhood = self.customer.neighborhood
            self.shipping_city = self.customer.city
            self.shipping_state = self.customer.state
        self.full_clean()
        super().save(*args, **kwargs)

    def update_total_value(self) -> Decimal:
        total = self.items.aggregate(
            total=Coalesce(
                Sum("subtotal"),
                Value(ZERO),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
        normalized_total = Decimal(total or ZERO).quantize(Decimal("0.01"))
        type(self).objects.filter(pk=self.pk).update(total_value=normalized_total)
        self.total_value = normalized_total
        return normalized_total


class OrderItem(models.Model):
    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.PROTECT,
        related_name="bakery_order_items",
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "bakery"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "order", "product"],
                name="uq_bakery_order_item_tenant_order_product",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="ck_bakery_order_item_quantity_positive",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "order"])]

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product.name} - Order #{self.order_id}"

    def clean(self) -> None:
        errors = {}
        if self.order_id and self.tenant_id != self.order.tenant_id:
            errors["order"] = "Order must belong to the item tenant."
        if self.product_id and self.tenant_id != self.product.tenant_id:
            errors["product"] = "Product must belong to the item tenant."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self._state.adding and self.unit_price == ZERO:
            # O preco e copiado apenas na criacao para manter o historico imutavel.
            self.unit_price = self.product.price
        self.subtotal = (self.unit_price * self.quantity).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
        self.order.update_total_value()

    def delete(self, *args, **kwargs):
        order = self.order
        result = super().delete(*args, **kwargs)
        order.update_total_value()
        return result