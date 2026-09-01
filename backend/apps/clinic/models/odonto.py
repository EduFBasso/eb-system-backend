from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.clinic.models.treatment import TreatmentPlanItem


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
