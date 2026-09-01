from django.db import models
# Importamos o TreatmentPlanItem porque a Podologia vai se pendurar na mesma estrutura de orçamento
from apps.clinic.models.treatment import TreatmentPlanItem

class PodologyProcedureContext(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Gerencia o contexto anatômico específico para procedimentos de Podologia.
    Conecta um item de orçamento (TreatmentPlanItem) a uma região exata dos Pés ou Mãos.
    """
    
    SCOPE_CHOICES = [
        ('pe_esquerdo', 'Pé Esquerdo'),
        ('pe_direito', 'Pé Direito'),
        ('mao_esquerda', 'Mão Esquerda'),
        ('mao_direita', 'Mão Direita'),
        ('geral', 'Geral / Outros (Não Anatômico)'),
    ]

    # Vinculação obrigatória ao ecossistema multi-tenant
    tenant = models.ForeignKey(
        'authentication.Tenant', 
        on_delete=models.CASCADE,
        verbose_name="Empresa/Inquilino"
    )

    # Relação One-to-One: Cada item de procedimento de podologia tem EXATAMENTE um contexto anatômico
    treatment_plan_item = models.OneToOneField(
        TreatmentPlanItem,
        on_delete=models.CASCADE,
        related_name='podology_context',
        verbose_name="Item do Plano de Tratamento"
    )

    # Define qual membro está recebendo o tratamento
    scope = models.CharField(
        "Escopo Anatômico",
        max_length=20,
        choices=SCOPE_CHOICES,
        default='geral'
    )

    # Identifica o dedo ou região clicada (Ex: 1 a 5 para artelhos/dedos)
    location_number = models.IntegerField(
        "Número da Localização / Dedo",
        null=True,
        blank=True,
        help_text="Número do dedo (1 a 5) ou região afetada no SVG do Frontend"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        db_table = 'clinic_podology_context'
        verbose_name = "Contexto de Procedimento de Podologia"
        verbose_name_plural = "Contextos de Procedimento de Podologia"

    def __str__(self):
        return f"{self.get_scope_display()} - Dedo/Região: {self.location_number or 'Geral'}"
