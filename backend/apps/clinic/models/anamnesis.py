from django.db import models


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


class AnamneseOdontologia(models.Model):
    """
    [SOLID - Open/Closed Principle]
    Estende a AnamneseBase para armazenar as respostas clínicas específicas da Odontologia.
    O núcleo comum do sistema permanece fechado para alterações, permitindo o isolamento
    técnico entre as especialidades médicas de forma limpa.
    """
    # Relacionamento 1 para 1 com a Base garante a extensão limpa do prontuário
    anamnese_base = models.OneToOneField(
        AnamneseBase,
        on_delete=models.CASCADE,
        related_name='odontologia',
        verbose_name='Anamnese Base',
    )
    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.CASCADE,
        related_name='anamneses_odontologia',
        verbose_name='Dentista Responsável',
    )

    # Campos específicos da Odontologia mapeados a partir do novo formulário do Frontend
    gum_bleeding = models.BooleanField("Gengiva sangra ao escovar?", default=False)
    floss_usage = models.BooleanField("Usa fio dental diariamente?", default=False)
    bruxism_clenching = models.BooleanField("Apresenta Bruxismo / Apertamento?", default=False)
    
    tooth_brushing_frequency = models.CharField(
        "Frequência de Escovação", 
        max_length=30, 
        blank=True, 
        default=""
    )
    chief_dental_complaint = models.TextField("Queixa Principal Bucal", blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Anamnese Especialidade - Odontologia'
        verbose_name_plural = 'Anamneses Especialidade - Odontologia'

    def __str__(self):
        return f'{self.anamnese_base.client} — Especificação Odontológica'
