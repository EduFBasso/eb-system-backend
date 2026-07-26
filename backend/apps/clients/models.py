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

    class Meta:
        app_label = 'clients'
        db_table = 'register_client'  # mantém a tabela existente

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def anamnese_base(self):
        cache = getattr(self, '_prefetched_objects_cache', {})
        prefetched = cache.get('anamneses_base')
        if prefetched is not None:
            for item in prefetched:
                if item.tenant_id == self.tenant_id and item.professional_id == self.professional_id:
                    return item

        return self.anamneses_base.filter(
            tenant_id=self.tenant_id,
            professional_id=self.professional_id,
        ).order_by('-updated_at', '-created_at').first()

    @property
    def anamnese_podologia(self):
        cache = getattr(self, '_prefetched_objects_cache', {})
        prefetched = cache.get('anamneses_podologia')
        if prefetched is not None:
            for item in prefetched:
                if item.tenant_id == self.tenant_id and item.professional_id == self.professional_id:
                    return item

        return self.anamneses_podologia.filter(
            tenant_id=self.tenant_id,
            professional_id=self.professional_id,
        ).order_by('-updated_at', '-created_at').first()
