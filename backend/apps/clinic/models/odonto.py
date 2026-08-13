from django.conf import settings
from django.db import models


class DentalArcade(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela o cabeçalho do Odontograma do paciente (Histórico de Tratamento Odontológico).
    Funciona como o contêiner principal que agrupa o estado da boca do cliente.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Plano de Tratamento Pendente'
        COMPLETED = 'completed', 'Tratamento Concluído'

    # [Garantia Multi-tenant] Vinculação explícita e obrigatória à clínica controladora
    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    
    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.CASCADE,
        related_name='dental_arcades',
        verbose_name='Dentista Responsável',
    )
    client = models.ForeignKey(
        'clinic.Client',
        on_delete=models.CASCADE,
        related_name='dental_arcades',
        verbose_name='Cliente/Paciente',
    )
    external_treatment_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='Chave primária (ID_PT_HEADER) importada da planilha/banco legado de 10 anos.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    started_at = models.DateField("Data de Início", null=True, blank=True)
    completed_at = models.DateField("Data de Conclusão", null=True, blank=True)
    notes = models.TextField("Anotações Gerais do Caso", blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Odonto - Arcada / Tratamento'
        verbose_name_plural = 'Odonto - Arcadas / Tratamentos'
        ordering = ['-updated_at']
        
        # Isola a integridade da migração legada por clínica
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'professional', 'external_treatment_id'],
                name='uniq_dental_arcade_migration_control'
            )
        ]
        indexes = [
            models.Index(fields=['tenant', 'professional', 'client']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f'Plano Odonto #{self.id} — Paciente: {self.client}'


class Tooth(models.Model):
    """
    [SOLID - Single Responsibility]
    Representa cada dente individual no mapa anatômico da boca daquele paciente específico.
    """
    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    arcade = models.ForeignKey(
        DentalArcade,
        on_delete=models.CASCADE,
        related_name='teeth',
        verbose_name='Tratamento/Arcada Mãe',
    )
    sequence = models.PositiveSmallIntegerField(
        help_text='Posição física sequencial no desenho visual da tela (1 a 32).',
    )
    international_number = models.PositiveSmallIntegerField(
        help_text='Notação Dentária Internacional de dois dígitos (FDI) — ex: 11 ao 48.',
    )
    external_arcade_row_id = models.BigIntegerField("ID Linha Legada", null=True, blank=True)
    observations = models.TextField("Observações Clínicas do Dente", blank=True, default='')
    
    # Campo inteligente para armazenar anomalias (Cárie, Canal, Pivot) usando bitwise/flags
    anomalies_bitmap = models.BigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Odonto - Dente'
        verbose_name_plural = 'Odonto - Dentes'
        ordering = ['sequence']
        
        constraints = [
            models.UniqueConstraint(
                fields=['arcade', 'sequence'],
                name='uniq_tooth_sequence_per_arcade'
            ),
            models.UniqueConstraint(
                fields=['arcade', 'international_number'],
                name='uniq_tooth_fdi_number_per_arcade'
            )
        ]
        indexes = [
            models.Index(fields=['arcade', 'sequence']),
            models.Index(fields=['arcade', 'international_number']),
        ]

    def __str__(self):
        return f'Dente {self.international_number} (Plano #{self.arcade_id})'


class Surface(models.Model):
    """
    [SOLID - Single Responsibility]
    Modela as divisões/faces de um dente (Faces Clínicas).
    Utilizado para detalhar tratamentos estritos em restaurações.
    """
    class SurfaceCode(models.TextChoices):
        O = 'O', 'Oclusal (Mastigação dentes traseiros)'
        PO = 'PO', 'Palatina/Oclusal'
        MO = 'MO', 'Mesial/Oclusal (Face lateral interna)'
        VO = 'VO', 'Vestibular/Oclusal (Face voltada para a bochecha)'
        LDI = 'LDI', 'Lingual/Distal/Incisal'

    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    tooth = models.ForeignKey(
        Tooth,
        on_delete=models.CASCADE,
        related_name='surfaces',
        verbose_name='Dente',
    )
    code = models.CharField("Código da Face", max_length=10, choices=SurfaceCode.choices)
    label = models.CharField("Rótulo / Descritivo Visual", max_length=40, blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Odonto - Face Dentária'
        verbose_name_plural = 'Odonto - Faces Dentárias'
        ordering = ['id']
        
        constraints = [
            models.UniqueConstraint(
                fields=['tooth', 'code'],
                name='uniq_surface_code_per_tooth'
            )
        ]
        indexes = [models.Index(fields=['tooth', 'code'])]

    def __str__(self):
        return f'Face {self.code} — Dente {self.tooth.international_number}'


class Procedure(models.Model):
    """
    [SOLID - Interface Segregation]
    Registra a ação/procedimento ou produto aplicado em um elemento anatômico da boca.
    Pode flutuar entre a arcada inteira, um dente isolado ou apenas uma face.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente (Orçado)'
        COMPLETED = 'completed', 'Concluído (Realizado)'
        CANCELED = 'canceled', 'Cancelado'

    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    arcade = models.ForeignKey(
        DentalArcade,
        on_delete=models.CASCADE,
        related_name='procedures',
        verbose_name='Plano de Tratamento',
    )
    tooth = models.ForeignKey(
        Tooth,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procedures',
        verbose_name='Dente Afetado',
    )
    surface = models.ForeignKey(
        Surface,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procedures',
        verbose_name='Face Afetada',
    )
    external_item_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='Código identificador da linha (ID_PT_ITEM) vindo da base legada.',
    )
    code = models.CharField("Código do Procedimento (TUSS/Interno)", max_length=40, blank=True, default='')
    name = models.CharField("Nome do Procedimento / Material", max_length=255)
    status = models.CharField(
        "Estado da Execução",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    region_raw = models.CharField(
        "Região Anatômica (Legado)",
        max_length=30,
        blank=True,
        default='',
        help_text='Texto bruto extraído da coluna TX_REGIAO durante a migração.',
    )
    faces_raw = models.CharField(
        "Faces Clínicas (Legado)",
        max_length=30,
        blank=True,
        default='',
        help_text='Texto bruto extraído da coluna TX_FACES durante a migração.',
    )
    started_at = models.DateField("Data Inicial", null=True, blank=True)
    completed_at = models.DateField("Data de Término", null=True, blank=True)
    
    # Camada financeira histórica da planilha legada
    patient_amount = models.DecimalField("Valor Orçado (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    paid_amount = models.DecimalField("Valor Pago pelo Paciente (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    paid_at = models.DateField("Data do Pagamento", null=True, blank=True)
    
    duration_minutes = models.PositiveSmallIntegerField("Tempo estimado (Minutos)", null=True, blank=True)
    notes = models.TextField("Notas de Execução Clínicas", blank=True, default='')
    is_active = models.BooleanField("Ativo?", default=True)
    is_product = models.BooleanField("É insumo/material consumível?", default=False)
    
    # Auto-relacionamento estruturado para vincular os materiais gastos em um determinado procedimento
    parent_procedure = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='products',
        help_text='Procedimento clínico principal ao qual este material de consumo está atrelado.',
        verbose_name="Procedimento Vinculado"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Odonto - Procedimento Realizado'
        verbose_name_plural = 'Odonto - Procedimentos Realizados'
        ordering = ['id']
        
        constraints = [
            models.UniqueConstraint(
                fields=['arcade', 'external_item_id'],
                name='uniq_procedure_item_migration_control')
                ]
        
        indexes = [
            models.Index(fields=['tenant', 'arcade', 'status']),
            models.Index(fields=['tenant', 'arcade', 'tooth']),
            ]

    def __str__(self):
        return f'{self.name} — Status: {self.get_status_display()}'


class ProcedureNameSuggestion(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Dicionário preditivo para o preenchimento rápido de nomes de procedimentos comuns da dentista.
    Evita que ela precise digitar o nome do procedimento do zero a cada consulta.
    """
    # [Garantia Multi-tenant] A lista de sugestões pertence à clínica controladora
    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    
    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.CASCADE,
        related_name='odonto_procedure_name_suggestions',
        verbose_name='Profissional',
    )
    name = models.CharField("Sugestão de Nome", max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Odonto - Sugestão de Nome de Procedimento'
        verbose_name_plural = 'Odonto - Sugestões de Nomes de Procedimentos'
        ordering = ['name']
        indexes = [
            # Otimiza a busca na tela combinando a clínica e o nome digitado
            models.Index(fields=['tenant', 'professional', 'name']),
        ]

    def __str__(self):
        return self.name


class ProductCatalogItem(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Catálogo histórico auxiliar utilizado durante a migração legada 
    para sugerir ou registrar os últimos valores praticados em insumos odontológicos.
    """
    # [Garantia Multi-tenant] O catálogo de apoio fica restrito à clínica correspondente
    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    
    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.CASCADE,
        related_name='odonto_product_catalog_items',
        verbose_name='Profissional',
    )
    name = models.CharField("Nome do Insumo / Material", max_length=255)
    
    # Armazena o último valor financeiro capturado da planilha histórica de 10 anos
    last_value = models.DecimalField(
        "Último Valor Registrado (R$)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Odonto - Item do Catálogo de Apoio'
        verbose_name_plural = 'Odonto - Itens do Catálogo de Apoio'
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'professional', 'name']),
        ]

    def __str__(self):
        return self.name
