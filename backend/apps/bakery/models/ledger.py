from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from .customers import BakeryCustomer, ZERO
from .orders import Order


class CreditLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        CREDIT = "CREDIT", "Credito/Deposito"
        DEBIT = "DEBIT", "Debito/Venda"

    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.PROTECT,
        related_name="bakery_credit_ledger_entries",
    )
    customer = models.ForeignKey(
        BakeryCustomer,
        on_delete=models.PROTECT,
        related_name="credit_ledger_entries",
    )
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_ledger_entries",
    )
    reference_key = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "bakery"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=ZERO),
                name="ck_bakery_ledger_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["tenant", "reference_key"],
                condition=~models.Q(reference_key=""),
                name="uq_bakery_ledger_tenant_reference_key",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "customer", "created_at"]),
            models.Index(fields=["tenant", "entry_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.customer.nickname} - {self.entry_type} R$ {self.amount:.2f}"

    def clean(self) -> None:
        errors = {}
        if self.amount is not None and Decimal(self.amount) <= ZERO:
            errors["amount"] = "Amount must be greater than zero."
        if self.customer_id and self.tenant_id != self.customer.tenant_id:
            errors["customer"] = "Customer must belong to the ledger tenant."
        if self.order_id:
            if self.tenant_id != self.order.tenant_id:
                errors["order"] = "Order must belong to the ledger tenant."
            elif self.customer_id != self.order.customer_id:
                errors["order"] = "Order must belong to the ledger customer."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Correcoes financeiras devem ser novos lancamentos, nunca alteracoes.
        if self.pk is not None:
            raise ValidationError("Credit ledger entries cannot be updated.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Credit ledger entries cannot be deleted.")