from django.db import models


class Client(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela o cadastro centralizado do Cliente/Paciente dentro de um Tenant (Clínica).
    O cliente é patrimônio da clínica, permitindo que ele seja atendido por múltiplos 
    profissionais (Podólogos, Dentistas, etc.) sem duplicar o registro no banco.
    """
    
    # Vinculação obrigatória ao ecossistema da clínica/empresa
    tenant = models.ForeignKey(
        'authentication.Tenant', 
        on_delete=models.CASCADE, 
        null=False, 
        blank=False,
        verbose_name="Empresa/Inquilino"
    )

    DOCUMENT_TYPE_CHOICES = [
        ("cpf", "CPF"),
        ("cnpj", "CNPJ"),
    ]

    SEX_CHOICES = [
        ("masculino", "Masculino"),
        ("feminino", "Feminino"),
        ("outro", "Outro"),
        ("nao_informado", "Prefiro não informar"),
    ]

    MARITAL_STATUS_CHOICES = [
        ("solteiro", "Solteiro(a)"),
        ("casado", "Casado(a)"),
        ("divorciado", "Divorciado(a)"),
        ("viuvo", "Viúvo(a)"),
        ("uniao_estavel", "União estável"),
    ]

    # Dados Pessoais de Identificação
    first_name = models.CharField("Primeiro nome", max_length=255)
    last_name = models.CharField("Sobrenome", max_length=255)
    
    # E-mail passa a ser único por Clínica (Tenant) para evitar conflitos de login/comunicação
    email = models.EmailField("E-mail", null=True, blank=True)
    
    # Telefone obrigatório e sem duplicidade por clínica, essencial para validação de links públicos (WhatsApp)
    phone = models.CharField("Telefone", max_length=20, null=False, blank=False)
    
    rg = models.CharField("RG", max_length=20, null=True, blank=True)
    document_type = models.CharField(
        "Tipo de documento", max_length=4,
        choices=DOCUMENT_TYPE_CHOICES, null=True, blank=True
    )
    document_number = models.CharField(
        "Número do documento", max_length=20, null=True, blank=True
    )
    sex = models.CharField(
        "Sexo", max_length=20, choices=SEX_CHOICES, null=True, blank=True
    )
    marital_status = models.CharField(
        "Estado civil", max_length=20, choices=MARITAL_STATUS_CHOICES, null=True, blank=True
    )
    nationality = models.CharField("Nacionalidade", max_length=60, null=True, blank=True)
    profession = models.CharField("Profissão", max_length=100, null=True, blank=True)

    # Dados de Localização e Endereço
    address = models.CharField("Endereço", max_length=255, null=True, blank=True)
    address_number = models.CharField("Número", max_length=16, null=True, blank=True)
    address_complement = models.CharField("Complemento", max_length=100, null=True, blank=True)
    neighborhood = models.CharField("Bairro", max_length=100, null=True, blank=True)
    city = models.CharField("Cidade", max_length=100, null=True, blank=True)
    state = models.CharField("Estado", max_length=2, null=True, blank=True)
    postal_code = models.CharField("CEP", max_length=20, null=True, blank=True)
    date_of_birth = models.DateField("Data de nascimento", null=True, blank=True)

    # Registros de Auditoria do Sistema
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        app_label = 'clinic'
        db_table = 'register_client'
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        
        constraints = [
            # [Garantia de Integridade] O mesmo telefone não pode se repetir na mesma clínica.
            # No entanto, clínicas diferentes (Tenants diferentes) podem ter o mesmo número de cliente.
            models.UniqueConstraint(
                fields=['tenant', 'phone'],
                name='uniq_client_tenant_phone'
            ),
            # Garante que se o e-mail for preenchido, ele também seja único dentro daquela clínica.
            models.UniqueConstraint(
                fields=['tenant', 'email'],
                name='uniq_client_tenant_email'
            )
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def latest_anamnesis_base(self):
        """
        [Abstração Genérica]
        Retorna a Ficha de Anamnese Geral mais recente deste cliente.
        Não importa qual especialidade ele vai passar, essa ficha unificada é retornada aqui.
        """
        return self.anamneses_base.filter(tenant_id=self.tenant_id).order_by('-updated_at').first()

    def get_specialized_anamnesis(self, specialty="podologia"):
        """
        [SOLID - Open/Closed Principle]
        Busca dinamicamente a extensão de anamnese técnica com base na especialidade.
        Se amanhã criarmos 'fisioterapia' ou 'nutricao', este método funcionará sem alterações.
        
        Exemplo de uso: meu_cliente.get_specialized_anamnesis('podologia')
        """
        base = self.latest_anamnesis_base
        if not base:
            return None
            
        # O Django permite acessar o OneToOneField usando letras minúsculas (related_name)
        # Se a propriedade correspondente à especialidade existir na Anamnese Geral, retorna ela.
        if hasattr(base, specialty):
            return getattr(base, specialty)
            
        return None


    # @property
    # def anamnese_base(self):
    #     cache = getattr(self, '_prefetched_objects_cache', {})
    #     prefetched = cache.get('anamneses_base')
    #     if prefetched is not None:
    #         for item in prefetched:
    #             if item.tenant_id == self.tenant_id and item.professional_id == self.professional_id:
    #                 return item

    #     return self.anamneses_base.filter(
    #         tenant_id=self.tenant_id,
    #         professional_id=self.professional_id,
    #     ).order_by('-updated_at', '-created_at').first()

    # @property
    # def anamnese_podologia(self):
    #     cache = getattr(self, '_prefetched_objects_cache', {})
    #     prefetched = cache.get('anamneses_podologia')
    #     if prefetched is not None:
    #         for item in prefetched:
    #             if item.tenant_id == self.tenant_id and item.professional_id == self.professional_id:
    #                 return item

    #     return self.anamneses_podologia.filter(
    #         tenant_id=self.tenant_id,
    #         professional_id=self.professional_id,
    #     ).order_by('-updated_at', '-created_at').first()
