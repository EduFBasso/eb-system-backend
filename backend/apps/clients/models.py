from django.db import models


class Client(models.Model):
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        "register.Professional",
        on_delete=models.CASCADE,
        related_name="clients",
        verbose_name="Profissional",
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

    # Pessoais
    first_name = models.CharField("Primeiro nome", max_length=255)
    last_name = models.CharField("Sobrenome", max_length=255)
    email = models.EmailField("E-mail", unique=True, null=True, blank=True)
    phone = models.CharField(
        "Telefone", max_length=20, unique=True, null=True, blank=False
    )
    rg = models.CharField(
        "RG", max_length=20, null=True, blank=True
    )
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
    nationality = models.CharField(
        "Nacionalidade", max_length=60, null=True, blank=True
    )
    profession = models.CharField("Profissão", max_length=100, null=True, blank=True)

    # Endereço
    address = models.CharField("Endereço", max_length=255, null=True, blank=True)
    neighborhood = models.CharField("Bairro", max_length=100, null=True, blank=True)
    city = models.CharField("Cidade", max_length=100, null=True, blank=True)
    state = models.CharField("Estado", max_length=2, null=True, blank=True)
    postal_code = models.CharField("CEP", max_length=20, null=True, blank=True)
    date_of_birth = models.DateField("Data de nascimento", null=True, blank=True)
    address_number = models.CharField("Número", max_length=16, null=True, blank=True)
    address_complement = models.CharField("Complemento", max_length=100, null=True, blank=True)

    # Registro
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    # Anamnese básica
    footwear_used = models.CharField("Calçado usado", max_length=50, null=True, blank=True)
    sock_used = models.CharField("Meia usada", max_length=50, null=True, blank=True)

    # Atividades acadêmicas e esportivas
    sport_activity = models.CharField("Atividade esportiva", max_length=50, null=True, blank=True)
    academic_activity = models.CharField("Atividade acadêmica", max_length=50, null=True, blank=True)

    # Anamnese médica
    takes_medication = models.CharField("Toma medicação", max_length=255, null=True, blank=True)
    had_surgery = models.CharField("Já fez cirurgia", max_length=255, null=True, blank=True)
    is_pregnant = models.BooleanField("Está grávida", null=True, blank=True)

    pain_sensitivity = models.CharField("Sensibilidade à dor", max_length=50, null=True, blank=True)
    clinical_history = models.TextField("Histórico clínico", null=True, blank=True)

    # Avaliação dos pés
    plantar_view_left = models.TextField("Vista plantar esquerda", null=True, blank=True)
    plantar_view_right = models.TextField("Vista plantar direita", null=True, blank=True)

    dermatological_pathologies_left = models.TextField("Patologias pé esquerdo", null=True, blank=True)
    dermatological_pathologies_right = models.TextField("Patologias pé direito", null=True, blank=True)

    nail_changes_left = models.TextField("Alterações nas unhas pé esquerdo", null=True, blank=True)
    nail_changes_right = models.TextField("Alterações nas unhas pé direito", null=True, blank=True)

    deformities_left = models.TextField("Deformidades pé esquerdo", null=True, blank=True)
    deformities_right = models.TextField("Deformidades pé direito", null=True, blank=True)

    sensitivity_test = models.TextField("Teste de sensibilidade", null=True, blank=True)
    other_procedures = models.TextField("Outros procedimentos", null=True, blank=True)

    class Meta:
        app_label = 'clients'
        db_table = 'register_client'  # mantém a tabela existente

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
