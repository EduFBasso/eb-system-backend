from django.conf import settings
from django.db import models


class DentalArcade(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        COMPLETED = 'completed', 'Concluido'

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        'register.Professional',
        on_delete=models.CASCADE,
        related_name='dental_arcades',
        verbose_name='Profissional',
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='dental_arcades',
        verbose_name='Cliente',
    )
    external_treatment_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='ID_PT_HEADER da base legada (quando aplicavel).',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    started_at = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'odonto'
        verbose_name = 'Arcada dentaria'
        verbose_name_plural = 'Arcadas dentarias'
        ordering = ['-updated_at']
        unique_together = [('professional', 'external_treatment_id')]
        indexes = [
            models.Index(fields=['professional', 'client']),
            models.Index(fields=['professional', 'status']),
        ]

    def __str__(self):
        return f'Arcada #{self.id} - {self.client}'


class Tooth(models.Model):
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    arcade = models.ForeignKey(
        DentalArcade,
        on_delete=models.CASCADE,
        related_name='teeth',
        verbose_name='Arcada',
    )
    sequence = models.PositiveSmallIntegerField(
        help_text='Posicao sequencial no mapa da arcada (1-32).',
    )
    international_number = models.PositiveSmallIntegerField(
        help_text='Numero internacional odontologico (11-48).',
    )
    external_arcade_row_id = models.BigIntegerField(null=True, blank=True)
    observations = models.TextField(blank=True, default='')
    anomalies_bitmap = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'odonto'
        verbose_name = 'Dente'
        verbose_name_plural = 'Dentes'
        ordering = ['sequence']
        unique_together = [
            ('arcade', 'sequence'),
            ('arcade', 'international_number'),
        ]
        indexes = [
            models.Index(fields=['arcade', 'sequence']),
            models.Index(fields=['arcade', 'international_number']),
        ]

    def __str__(self):
        return f'Dente {self.international_number} (Arcada {self.arcade_id})'


class Surface(models.Model):
    class SurfaceCode(models.TextChoices):
        O = 'O', 'Oclusal'
        PO = 'PO', 'Palatina/Oclusal'
        MO = 'MO', 'Mesial/Oclusal'
        VO = 'VO', 'Vestibular/Oclusal'
        LDI = 'LDI', 'Lingual/Distal/Incisal'

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    tooth = models.ForeignKey(
        Tooth,
        on_delete=models.CASCADE,
        related_name='surfaces',
        verbose_name='Dente',
    )
    code = models.CharField(max_length=10, choices=SurfaceCode.choices)
    label = models.CharField(max_length=40, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'odonto'
        verbose_name = 'Face'
        verbose_name_plural = 'Faces'
        ordering = ['id']
        unique_together = [('tooth', 'code')]
        indexes = [models.Index(fields=['tooth', 'code'])]

    def __str__(self):
        return f'Face {self.code} ({self.tooth})'


class Procedure(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        COMPLETED = 'completed', 'Concluido'
        CANCELED = 'canceled', 'Cancelado'

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    arcade = models.ForeignKey(
        DentalArcade,
        on_delete=models.CASCADE,
        related_name='procedures',
        verbose_name='Arcada',
    )
    tooth = models.ForeignKey(
        Tooth,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procedures',
        verbose_name='Dente',
    )
    surface = models.ForeignKey(
        Surface,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procedures',
        verbose_name='Face',
    )
    external_item_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='ID_PT_ITEM da base legada (quando aplicavel).',
    )
    code = models.CharField(max_length=40, blank=True, default='')
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    region_raw = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text='Valor original importado de TX_REGIAO.',
    )
    faces_raw = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text='Valor original importado de TX_FACES.',
    )
    started_at = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)
    patient_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    paid_at = models.DateField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_product = models.BooleanField(default=False, help_text='Se True, é um produto/material; se False, é um procedimento')
    parent_procedure = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='products',
        help_text='Procedimento pai ao qual este produto esta vinculado.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'odonto'
        verbose_name = 'Procedimento odontologico'
        verbose_name_plural = 'Procedimentos odontologicos'
        ordering = ['id']
        unique_together = [('arcade', 'external_item_id')]
        indexes = [
            models.Index(fields=['arcade', 'status']),
            models.Index(fields=['arcade', 'tooth']),
            models.Index(fields=['external_item_id']),
        ]

    def __str__(self):
        return f'{self.name} ({self.status})'


class ProcedureNameSuggestion(models.Model):
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='odonto_procedure_name_suggestions',
        verbose_name='Profissional',
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'odonto'
        verbose_name = 'Sugestao de nome de procedimento'
        verbose_name_plural = 'Sugestoes de nomes de procedimento'
        ordering = ['name']
        indexes = [
            models.Index(fields=['professional', 'name']),
        ]

    def __str__(self):
        return self.name


class ProductCatalogItem(models.Model):
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='odonto_product_catalog_items',
        verbose_name='Profissional',
    )
    name = models.CharField(max_length=255)
    last_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'odonto'
        verbose_name = 'Item de catalogo de produto'
        verbose_name_plural = 'Itens de catalogo de produto'
        ordering = ['name']
        indexes = [
            models.Index(fields=['professional', 'name']),
        ]

    def __str__(self):
        return self.name
