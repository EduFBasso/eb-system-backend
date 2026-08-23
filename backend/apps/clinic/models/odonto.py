from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


# ─────────────────────────────────────────────────────────────────────────────
# Plano de Tratamento Odontológico
# ─────────────────────────────────────────────────────────────────────────────

class TreatmentPlan(models.Model):
    """
    Container principal do odontograma do paciente.
    Representa um ciclo de tratamento. Um paciente pode ter múltiplos planos abertos.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Em Tratamento'
        COMPLETED = 'completed', 'Tratamento Concluído'
        ARCHIVED = 'archived', 'Arquivado'
        CANCELLED = 'cancelled', 'Cancelado'

    class PaymentCondition(models.TextChoices):
        CASH = 'avista', 'À Vista'
        INSTALLMENTS = 'aprazo', 'A Prazo'

    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.CASCADE,
        related_name='treatment_plans',
        verbose_name='Dentista Responsável',
    )
    client = models.ForeignKey(
        'clinic.Client',
        on_delete=models.CASCADE,
        related_name='treatment_plans',
        verbose_name='Paciente',
    )
    name = models.CharField('Nome do Plano', max_length=120, blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_printed = models.BooleanField(
        'Impresso',
        default=False,
        help_text='Trava o plano contra edição/exclusão após a impressão do orçamento.',
    )
    printed_at = models.DateTimeField(
        'Data da impressão',
        null=True,
        blank=True,
        help_text='Momento em que o orçamento foi confirmado como impresso e travado.',
    )
    started_at = models.DateField('Data de Início', null=True, blank=True)
    completed_at = models.DateField('Data de Conclusão', null=True, blank=True)
    payment_condition = models.CharField(
        'Condição de Pagamento',
        max_length=10,
        choices=PaymentCondition.choices,
        default=PaymentCondition.CASH,
    )
    installments_count = models.PositiveSmallIntegerField(
        'Número de Parcelas',
        default=2,
    )
    first_due_date = models.DateField(
        'Vencimento da Primeira Parcela',
        null=True,
        blank=True,
    )
    notes = models.TextField('Anotações Gerais do Caso', blank=True, default='')
    external_treatment_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='ID_PT_HEADER importado do banco legado.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Plano de Tratamento Odontológico'
        verbose_name_plural = 'Planos de Tratamento Odontológico'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'professional', 'external_treatment_id'],
                condition=Q(external_treatment_id__isnull=False),
                name='uniq_treatment_plan_migration_control',
            ),
            models.CheckConstraint(
                check=~Q(status='completed') | Q(completed_at__isnull=False),
                name='treatment_plan_completed_requires_completed_at',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'professional', 'client']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f'Plano #{self.id} — {self.client}'


# ─────────────────────────────────────────────────────────────────────────────
# Item do Plano de Tratamento
# ─────────────────────────────────────────────────────────────────────────────

class TreatmentPlanItem(models.Model):
    """
    Registro de um procedimento clínico ou insumo dentro de um plano de tratamento.
    Consome o catálogo de Service/Product já existente no core do clinic,
    eliminando os catálogos paralelos ProcedureNameSuggestion e ProductCatalogItem.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente (Orçado)'
        COMPLETED = 'completed', 'Concluído (Realizado)'
        CANCELED = 'canceled', 'Cancelado'

    class ItemKind(models.TextChoices):
        SERVICE = 'service', 'Procedimento / Serviço'
        PRODUCT = 'product', 'Insumo / Material Consumível'

    plan = models.ForeignKey(
        TreatmentPlan,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Plano de Tratamento',
    )
    # tenant/client/professional herdados via plan — sem FK redundante nos filhos
    kind = models.CharField(
        'Tipo de Item',
        max_length=10,
        choices=ItemKind.choices,
        default=ItemKind.SERVICE,
    )
    service = models.ForeignKey(
        'clinic.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='treatment_items',
        verbose_name='Serviço do Catálogo',
    )
    product = models.ForeignKey(
        'clinic.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='treatment_items',
        verbose_name='Produto do Catálogo',
    )
    custom_name = models.CharField(
        'Nome Personalizado',
        max_length=255,
        blank=True,
        default='',
        help_text='Preenchido apenas quando não há serviço ou produto no catálogo.',
    )
    status = models.CharField(
        'Status de Execução',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    patient_price = models.DecimalField(
        'Valor Orçado ao Paciente (R$)',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    started_at = models.DateField('Data Inicial', null=True, blank=True)
    completed_at = models.DateField('Data de Conclusão', null=True, blank=True)
    notes = models.TextField('Notas Clínicas', blank=True, default='')
    is_active = models.BooleanField('Ativo?', default=True)
    external_item_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='ID_PT_ITEM do banco legado.',
    )
    # materiais de consumo podem ser vinculados a um procedimento pai
    parent_item = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_items',
        verbose_name='Item Pai (Procedimento)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Item do Plano de Tratamento'
        verbose_name_plural = 'Itens do Plano de Tratamento'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['plan', 'external_item_id'],
                condition=Q(external_item_id__isnull=False),
                name='uniq_treatment_item_migration_control',
            ),
            models.CheckConstraint(
                check=~Q(status='completed') | Q(completed_at__isnull=False),
                name='treatment_item_completed_requires_completed_at',
            ),
        ]
        indexes = [
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['plan', 'kind']),
        ]

    def clean(self):
        has_service = self.service_id is not None
        has_product = self.product_id is not None
        has_custom = bool(self.custom_name)
        sources = sum([has_service, has_product, has_custom])
        if sources == 0:
            raise ValidationError(
                'O item deve ter um serviço, produto ou nome personalizado preenchido.'
            )
        if sources > 1:
            raise ValidationError(
                'O item deve referenciar apenas uma origem: serviço, produto ou nome personalizado.'
            )
        if self.kind == self.ItemKind.PRODUCT and has_service:
            raise ValidationError({'kind': 'Item do tipo produto não pode referenciar um serviço.'})
        if self.kind == self.ItemKind.SERVICE and has_product:
            raise ValidationError({'kind': 'Item do tipo serviço não pode referenciar um produto.'})

    def __str__(self):
        if self.service_id:
            return f'{self.service.name} — {self.get_status_display()}'  # type: ignore[union-attr]
        if self.product_id:
            return f'{self.product.name} — {self.get_status_display()}'  # type: ignore[union-attr]
        return f'{self.custom_name} — {self.get_status_display()}'


# ─────────────────────────────────────────────────────────────────────────────
# Contexto Anatômico Dentário — extensão one-to-one de TreatmentPlanItem
# ─────────────────────────────────────────────────────────────────────────────

# Intervalos válidos da notação FDI/ISO 3950
_FDI_VALID_CHECK = (
    Q(tooth_number__isnull=True)
    | Q(tooth_number__gte=11, tooth_number__lte=18)
    | Q(tooth_number__gte=21, tooth_number__lte=28)
    | Q(tooth_number__gte=31, tooth_number__lte=38)
    | Q(tooth_number__gte=41, tooth_number__lte=48)
    | Q(tooth_number__gte=51, tooth_number__lte=55)
    | Q(tooth_number__gte=61, tooth_number__lte=65)
    | Q(tooth_number__gte=71, tooth_number__lte=75)
    | Q(tooth_number__gte=81, tooth_number__lte=85)
)

_VALID_FDI_RANGES: tuple[tuple[int, int], ...] = (
    (11, 18), (21, 28), (31, 38), (41, 48),  # permanentes
    (51, 55), (61, 65), (71, 75), (81, 85),  # decíduos
)


def _is_valid_fdi(number: int) -> bool:
    return any(lo <= number <= hi for lo, hi in _VALID_FDI_RANGES)


class DentalProcedureContext(models.Model):
    """
    Extensão anatômica de um item do plano de tratamento.
    Herda tenant, client e professional do TreatmentPlanItem pai por design
    (sem duplicação de FKs, evitando inconsistências multi-tenant).
    """
    class Scope(models.TextChoices):
        TOOTH = 'tooth', 'Dente Específico'
        ARCH = 'arch', 'Arcada Inteira'
        FULL = 'full', 'Boca Toda'

    class ArchSide(models.TextChoices):
        SUPERIOR = 'superior', 'Arcada Superior'
        INFERIOR = 'inferior', 'Arcada Inferior'

    class ToothSurface(models.TextChoices):
        OCCLUSAL = 'O', 'Oclusal'
        MESIAL = 'M', 'Mesial'
        DISTAL = 'D', 'Distal'
        VESTIBULAR = 'V', 'Vestibular'
        LINGUAL = 'L', 'Lingual / Palatino'
        INCISAL = 'I', 'Incisal'

    item = models.OneToOneField(
        TreatmentPlanItem,
        on_delete=models.CASCADE,
        related_name='dental_context',
        verbose_name='Item do Plano',
    )
    scope = models.CharField(
        'Escopo Anatômico',
        max_length=10,
        choices=Scope.choices,
        default=Scope.TOOTH,
    )
    tooth_number = models.PositiveSmallIntegerField(
        'Número FDI do Dente',
        null=True,
        blank=True,
        help_text='Notação FDI/ISO 3950: 11–48 permanentes, 51–85 decíduos.',
    )
    tooth_surface = models.CharField(
        'Face(s) Clínica(s)',
        max_length=20,
        blank=True,
        default='',
        help_text='Uma ou mais faces separadas por vírgula: O, M, D, V, L, I.',
    )
    arcade_arch = models.CharField(
        'Arcada',
        max_length=10,
        choices=ArchSide.choices,
        null=True,
        blank=True,
    )
    observations = models.TextField('Observações do Dente', blank=True, default='')

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Contexto Anatômico Dentário'
        verbose_name_plural = 'Contextos Anatômicos Dentários'
        constraints = [
            models.CheckConstraint(
                check=_FDI_VALID_CHECK,
                name='dental_context_valid_fdi_tooth_number',
            ),
            models.CheckConstraint(
                check=~Q(scope='tooth') | Q(tooth_number__isnull=False),
                name='dental_context_tooth_scope_requires_number',
            ),
            models.CheckConstraint(
                check=~Q(scope='arch') | Q(arcade_arch__isnull=False),
                name='dental_context_arch_scope_requires_arch',
            ),
        ]
        indexes = [
            models.Index(fields=['item', 'scope']),
            models.Index(fields=['tooth_number']),
        ]

    def clean(self):
        errors = {}
        if self.scope == self.Scope.TOOTH and not self.tooth_number:
            errors['tooth_number'] = (
                'Escopo "dente específico" requer o número FDI do dente.'
            )
        if self.scope == self.Scope.ARCH and not self.arcade_arch:
            errors['arcade_arch'] = (
                'Escopo "arcada inteira" requer a indicação da arcada (superior/inferior).'
            )
        if self.tooth_number and not _is_valid_fdi(self.tooth_number):
            errors['tooth_number'] = (
                f'{self.tooth_number} não é um número FDI válido. '
                'Use 11–48 para permanentes ou 51–85 para decíduos.'
            )
        if self.tooth_surface:
            valid_codes = {c.value for c in self.ToothSurface}
            invalid = [f.strip() for f in self.tooth_surface.split(',') if f.strip() not in valid_codes]
            if invalid:
                errors['tooth_surface'] = (
                    f"Face(s) inválida(s): {', '.join(invalid)}. "
                    f"Aceitos: {', '.join(sorted(valid_codes))}."
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        if self.scope == self.Scope.TOOTH and self.tooth_number:
            suffix = f' [{self.tooth_surface}]' if self.tooth_surface else ''
            return f'Dente {self.tooth_number}{suffix}'
        if self.scope == self.Scope.ARCH:
            return f'Arcada {self.get_arcade_arch_display()}'
        return 'Boca Toda'
