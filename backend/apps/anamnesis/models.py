from django.db import models
from django.utils.text import slugify


class AnamneseBase(models.Model):
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='anamneses_base',
        verbose_name='Cliente',
    )
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='anamneses_base',
        verbose_name='Tenant',
    )
    professional = models.ForeignKey(
        'register.Professional',
        on_delete=models.CASCADE,
        related_name='anamneses_base',
        verbose_name='Profissional',
    )
    takes_medication = models.CharField('Toma medicação', max_length=255, null=True, blank=True)
    had_surgery = models.CharField('Já fez cirurgia', max_length=255, null=True, blank=True)
    is_pregnant = models.BooleanField('Está grávida', null=True, blank=True)
    pain_sensitivity = models.CharField('Sensibilidade à dor', max_length=50, null=True, blank=True)
    clinical_history = models.TextField('Histórico clínico', null=True, blank=True)
    sport_activity = models.CharField('Atividade esportiva', max_length=50, null=True, blank=True)
    academic_activity = models.CharField('Atividade acadêmica', max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'anamnesis'
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Anamnese base'
        verbose_name_plural = 'Anamneses base'
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'tenant', 'professional'],
                name='uniq_anamnese_base_client_tenant_professional',
            ),
        ]

    def __str__(self):
        return f'{self.client} — Anamnese base'


class AnamnesePodologia(models.Model):
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='anamneses_podologia',
        verbose_name='Cliente',
    )
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='anamneses_podologia',
        verbose_name='Tenant',
    )
    professional = models.ForeignKey(
        'register.Professional',
        on_delete=models.CASCADE,
        related_name='anamneses_podologia',
        verbose_name='Profissional',
    )
    footwear_used = models.CharField('Calçado usado', max_length=50, null=True, blank=True)
    sock_used = models.CharField('Meia usada', max_length=50, null=True, blank=True)
    plantar_view_left = models.TextField('Vista plantar esquerda', null=True, blank=True)
    plantar_view_right = models.TextField('Vista plantar direita', null=True, blank=True)
    dermatological_pathologies_left = models.TextField('Patologias pé esquerdo', null=True, blank=True)
    dermatological_pathologies_right = models.TextField('Patologias pé direito', null=True, blank=True)
    nail_changes_left = models.TextField('Alterações nas unhas pé esquerdo', null=True, blank=True)
    nail_changes_right = models.TextField('Alterações nas unhas pé direito', null=True, blank=True)
    deformities_left = models.TextField('Deformidades pé esquerdo', null=True, blank=True)
    deformities_right = models.TextField('Deformidades pé direito', null=True, blank=True)
    sensitivity_test = models.TextField('Teste de sensibilidade', null=True, blank=True)
    other_procedures = models.TextField('Outros procedimentos', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'anamnesis'
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Anamnese podologia'
        verbose_name_plural = 'Anamneses podologia'
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'tenant', 'professional'],
                name='uniq_anamnese_podologia_client_tenant_professional',
            ),
        ]

    def __str__(self):
        return f'{self.client} — Anamnese podologia'


class AnamnesisField(models.Model):
    """
    Defines a question/field in the anamnesis form for a specific professional.
    Each professional has their own set of fields, grouped by sector.
    """

    FIELD_TYPE_CHOICES = [
        ('radio', 'Radio buttons'),
        ('text', 'Texto livre'),
        ('textarea', 'Texto longo'),
    ]

    SELECTION_MODE_CHOICES = [
        ('single', 'Seleção única'),
        ('multiple', 'Seleção múltipla'),
    ]

    professional = models.ForeignKey(
        'register.Professional',
        on_delete=models.CASCADE,
        related_name='anamnesis_fields',
        verbose_name='Profissional',
    )
    code = models.SlugField(
        'Código',
        max_length=120,
        blank=True,
        help_text='Identificador estável do campo para seeds, migrações e lógica de dependência.',
    )
    sector = models.CharField(
        'Setor',
        max_length=100,
        help_text='Agrupa visualmente os campos — ex: "Histórico", "Pé Direito"',
    )
    sector_order = models.PositiveSmallIntegerField(
        'Ordem do setor',
        default=0,
        help_text='Ordem de exibição do setor na tela',
    )
    label = models.CharField('Pergunta', max_length=200)
    field_type = models.CharField(
        'Tipo',
        max_length=10,
        choices=FIELD_TYPE_CHOICES,
        default='radio',
    )
    selection_mode = models.CharField(
        'Modo de seleção',
        max_length=10,
        choices=SELECTION_MODE_CHOICES,
        default='single',
        help_text='Use multiple para campos de checklist com concatenação textual.',
    )
    options = models.JSONField(
        'Opções',
        null=True,
        blank=True,
        help_text='Lista de strings para radio buttons. Null para text/textarea.',
    )
    placeholder = models.CharField(
        'Placeholder',
        max_length=200,
        blank=True,
        default='',
        help_text='Texto de apoio opcional para campos text/textarea.',
    )
    depends_on = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_fields',
        verbose_name='Depende de',
        help_text='Campo pai que controla a visibilidade deste campo.',
    )
    show_when_value = models.CharField(
        'Exibir quando valor for',
        max_length=100,
        blank=True,
        default='',
        help_text='Valor do campo pai que deve habilitar este campo. Vazio = qualquer valor não vazio.',
    )
    order = models.PositiveSmallIntegerField(
        'Ordem dentro do setor',
        default=0,
    )
    is_active = models.BooleanField(
        'Ativo',
        default=True,
        help_text='Desativar em vez de apagar preserva respostas históricas.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'anamnesis'
        ordering = ['sector_order', 'order']
        unique_together = [('professional', 'code')]
        verbose_name = 'Campo de anamnese'
        verbose_name_plural = 'Campos de anamnese'

    def save(self, *args, **kwargs):
        if not self.code:
            base_code = slugify(self.label).replace('-', '_') or 'anamnesis_field'
            candidate = base_code
            suffix = 2
            while AnamnesisField.objects.filter(
                professional=self.professional,
                code=candidate,
            ).exclude(pk=self.pk).exists():
                candidate = f'{base_code}_{suffix}'
                suffix += 1
            self.code = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f'[{self.sector}] {self.label} ({self.professional})'


class AnamnesisResponse(models.Model):
    """
    Records a patient's answer to one anamnesis field at a point in time.
    field_label_snap preserves the question text even if the field is later renamed/deleted.
    """

    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='anamnesis_responses',
        verbose_name='Cliente',
    )
    field = models.ForeignKey(
        AnamnesisField,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responses',
        verbose_name='Campo',
    )
    field_label_snap = models.CharField(
        'Pergunta (snapshot)',
        max_length=200,
        help_text='Cópia do label no momento da resposta.',
    )
    value = models.TextField('Resposta', blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'anamnesis'
        # One response per client per field
        unique_together = [('client', 'field')]
        verbose_name = 'Resposta de anamnese'
        verbose_name_plural = 'Respostas de anamnese'

    def __str__(self):
        field_info = self.field_label_snap or (str(self.field) if self.field else 'campo excluído')
        return f'{self.client} — {field_info}: {self.value[:40]}'
