from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce


ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)


class BakeryCustomer(models.Model):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "PF", "Pessoa fisica"
        COMPANY = "PJ", "Pessoa juridica"

    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDENTE", "Pendente de aprovacao"
        APPROVED = "APROVADO", "Aprovado"
        BLOCKED = "BLOQUEADO", "Bloqueado"

    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.PROTECT,
        related_name="bakery_customers",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bakery_customer_profiles",
    )
    status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    customer_type = models.CharField(
        max_length=2,
        choices=CustomerType.choices,
        default=CustomerType.COMPANY,
    )
    nickname = models.CharField(max_length=100)
    company_name = models.CharField(max_length=150, blank=True)
    cpf = models.CharField(
        max_length=11,
        blank=True,
        validators=[RegexValidator(r"^\d{11}$", "CPF must contain 11 digits.")],
    )
    cnpj = models.CharField(
        max_length=14,
        blank=True,
        validators=[RegexValidator(r"^\d{14}$", "CNPJ must contain 14 digits.")],
    )
    phone = models.CharField(
        max_length=11,
        validators=[RegexValidator(r"^\d{10,11}$", "Phone must contain 10 or 11 digits.")],
    )
    zip_code = models.CharField(
        max_length=8,
        validators=[RegexValidator(r"^\d{8}$", "ZIP code must contain 8 digits.")],
    )
    street = models.CharField(max_length=150)
    number = models.CharField(max_length=20)
    complement = models.CharField(max_length=100, blank=True)
    neighborhood = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)

    # Limite acordado manualmente pelo dono da panificadora com o cliente B2B.
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_bakery_customers",
    )
    blocked_at = models.DateTimeField(null=True, blank=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocked_bakery_customers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "bakery"
        ordering = ["nickname"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user"],
                name="uq_bakery_customer_tenant_user",
            ),
            models.UniqueConstraint(
                fields=["tenant", "cpf"],
                condition=~Q(cpf=""),
                name="uq_bakery_customer_tenant_cpf",
            ),
            models.UniqueConstraint(
                fields=["tenant", "cnpj"],
                condition=~Q(cnpj=""),
                name="uq_bakery_customer_tenant_cnpj",
            ),
            models.CheckConstraint(
                condition=Q(credit_limit__gte=ZERO),
                name="ck_bakery_customer_credit_limit_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "nickname"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.nickname} ({self.get_customer_type_display()})"

    @property
    def is_approved(self) -> bool:
        return self.status == self.ApprovalStatus.APPROVED

    def _ledger_totals(self) -> tuple[Decimal, Decimal]:
        totals = self.credit_ledger_entries.aggregate(
            debit=Coalesce(
                Sum("amount", filter=Q(entry_type="DEBIT")),
                Value(ZERO),
                output_field=MONEY_FIELD,
            ),
            credit=Coalesce(
                Sum("amount", filter=Q(entry_type="CREDIT")),
                Value(ZERO),
                output_field=MONEY_FIELD,
            ),
        )
        return totals["debit"] or ZERO, totals["credit"] or ZERO

    def get_balance(self) -> Decimal:
        """Retorna o valor utilizado: vendas menos pagamentos/liberacoes."""

        debit, credit = self._ledger_totals()
        return (debit - credit).quantize(Decimal("0.01"))

    @property
    def financial_limit(self) -> Decimal:
        return Decimal(self.credit_limit or ZERO).quantize(Decimal("0.01"))

    @property
    def financial_used(self) -> Decimal:
        return max(self.get_balance(), ZERO)

    @property
    def financial_available(self) -> Decimal:
        return max(self.financial_limit - self.financial_used, ZERO)

    @property
    def current_balance(self) -> Decimal:
        return self.financial_used

    @property
    def available_credit(self) -> Decimal:
        return self.financial_available

    def can_make_orders(self) -> bool:
        return (
            self.is_approved
            and self.financial_limit > ZERO
            and self.financial_available > ZERO
        )

    def can_reserve_credit(self, amount: Decimal) -> bool:
        normalized_amount = Decimal(amount).quantize(Decimal("0.01"))
        return self.can_make_orders() and normalized_amount > ZERO and (
            normalized_amount <= self.financial_available
        )


class BakeryCustomerAuditLog(models.Model):
    class Action(models.TextChoices):
        APPROVED = "APPROVED", "Cliente aprovado"
        BLOCKED = "BLOCKED", "Cliente bloqueado"
        CREDIT_LIMIT_UPDATED = "CREDIT_LIMIT_UPDATED", "Limite atualizado"
        UNBLOCKED = "UNBLOCKED", "Cliente desbloqueado"

    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.PROTECT,
        related_name="bakery_customer_audit_logs",
    )
    customer = models.ForeignKey(
        BakeryCustomer,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="bakery_customer_audit_actions",
    )
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "bakery"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "customer", "created_at"]),
            models.Index(fields=["tenant", "action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.customer.nickname} - {self.get_action_display()}"