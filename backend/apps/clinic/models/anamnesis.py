from django.db import models
from django.utils.text import slugify


class AnamneseBase(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Guarda EXCLUSIVAMENTE o histórico clínico global do cliente que não muda
    independente da especialidade médica (Podologia, Odonto, Geral).
    """
    client = models.ForeignKey(
        'clinic.Client',
        on_delete=models.CASCADE,
        related_name='anamneses_base',
        verbose_name='Cliente',
    )
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        related_name='anamneses_base',
        verbose_name='Tenant (Clínica)',
    )

    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.SET_NULL,  # Se o profissional for deletado, a anamnese continua existindo
        null=True,                  # Permite ficar vazio se o próprio cliente preencher via link público
        blank=True,                 # Permite salvar sem preencher no painel admin
        related_name='anamneses_base',
        verbose_name='Profissional Responsável',
    )
    
    # Campos clínicos globais (Fixos para qualquer saúde)
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
        app_label = 'clinic'
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Anamnese Geral'
        verbose_name_plural = 'Anamneses Gerais'
        constraints = [
            # Um cliente possui apenas UMA anamnese geral por clínica (Tenant)
            models.UniqueConstraint(
                fields=['client', 'tenant'],
                name='uniq_anamnese_base_client_tenant',
            ),
        ]

    def __str__(self):
        return f'{self.client} — Anamnese Geral'


class AnamnesePodologia(models.Model):
    """
    [SOLID - Open/Closed Principle]
    Esta tabela estende a AnamneseBase. Se o cliente for na podóloga,
    criamos este registro. Se for na dentista, este fica vazio e cria-se o de Odonto.
    O núcleo (AnamneseBase) nunca precisa ser modificado para novas especialidades.
    """
    # Relacionamento 1 para 1 com a Base garante a extensão limpa dos dados
    anamnese_base = models.OneToOneField(
        AnamneseBase,
        on_delete=models.CASCADE,
        related_name='podologia',
        verbose_name='Anamnese Base',
    )
    # Armazena qual profissional de podologia preencheu esta parte técnica
    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.CASCADE,
        related_name='anamneses_podologia',
        verbose_name='Podólogo(a)',
    )
    
    # Campos exclusivos da Podologia
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
        app_label = 'clinic'
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Anamnese Especialidade - Podologia'
        verbose_name_plural = 'Anamneses Especialidade - Podologia'

    def __str__(self):
        return f'{self.anamnese_base.client} — Especificação Podologia'


class AnamnesisField(models.Model):
    """
    Estrutura para perguntas dinâmicas (Custom Fields).
    Útil caso queira criar perguntas na tela sem mexer em tabelas do banco.
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
        'authentication.Professional',
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
        help_text='Desativar preserva o histórico médico antigo.',
    )

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Campo de Anamnese Customizado'
        verbose_name_plural = 'Campos de Anamnese Customizados'

    def save(self, *args, **kwargs):
        if not self.code and self.label:
            self.code = slugify(self.label)[:120]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.label} ({self.professional})'


class AnamnesisResponse(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Grava o histórico exato da resposta de um paciente para uma pergunta dinâmica.
    O campo field_label_snap preserva o texto original da pergunta feita no passado,
    garantindo a segurança jurídica dos dados médicos mesmo se a pergunta mudar depois.
    """

    client = models.ForeignKey(
        'clinic.Client',
        on_delete=models.CASCADE,
        related_name='anamnesis_responses',
        verbose_name='Cliente',
    )
    field = models.ForeignKey(
        AnamnesisField,
        on_delete=models.SET_NULL, # Preserva a resposta histórica mesmo se o campo for apagado
        null=True,
        blank=True,
        related_name='responses',
        verbose_name='Campo Dinâmico',
    )
    field_label_snap = models.CharField(
        'Pergunta (Histórico)',
        max_length=200,
        help_text='Cópia fiel da pergunta no momento exato em que foi respondida.',
    )
    value = models.TextField('Resposta', blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = 'Resposta de Anamnese Customizada'
        verbose_name_plural = 'Respostas de Anamneses Customizadas'
        constraints = [
            # Garante que um cliente tenha apenas uma resposta registrada para cada campo específico
            models.UniqueConstraint(
                fields=['client', 'field'],
                name='uniq_anamnesis_response_client_field',
            ),
        ]

    def __str__(self):
        field_info = self.field_label_snap or (str(self.field) if self.field else 'Campo excluído')
        return f'{self.client} — {field_info}: {self.value[:40]}'
