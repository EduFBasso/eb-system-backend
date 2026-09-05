from django.db import models


class TelegramProfessionalLink(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela as credenciais e o canal de comunicação do Telegram de um Profissional.
    Permite que cada profissional configure o token do seu próprio Bot (BotFather)
    para interagir de forma isolada e privada, independente de qual ecossistema
    (clinic, bakery, etc.) o esteja utilizando.
    """
    # [Garantia Multi-tenant] Vincula o canal de comunicação ao tenant
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        verbose_name="Clínica/Tenant"
    )

    professional = models.OneToOneField(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="telegram_link",
        verbose_name="Profissional",
    )

    # [Configuração do BotFather Individual]
    # Guarda o Token secreto gerado pelo profissional para o seu próprio Bot.
    # Exemplo: '123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ'
    bot_token = models.CharField(
        "Token do Bot (BotFather)",
        max_length=120,
        blank=True,
        null=True,
        help_text="Insira o token privado do seu Bot do Telegram caso queira usar um bot próprio."
    )

    chat_id = models.CharField(
        "ID do Chat / Canal",
        max_length=64,
        help_text="Identificador numérico do chat privado ou grupo para onde os alertas serão enviados."
    )

    telegram_username = models.CharField("Username no Telegram (@)", max_length=64, blank=True)
    is_active = models.BooleanField("Vínculo Ativo?", default=True)
    linked_at = models.DateTimeField("Vinculado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)
    last_error = models.TextField("Último Erro de Conexão/Envio", blank=True)

    class Meta:
        app_label = 'notifications'
        # Nome físico preservado da migração original em apps.clinic (mesma tabela, sem migração de dados).
        db_table = 'clinic_telegramprofessionallink'
        verbose_name = "Vínculo Telegram"
        verbose_name_plural = "Vínculos Telegram"

        constraints = [
            # Garante que um mesmo ID de chat não seja duplicado dentro do mesmo tenant
            models.UniqueConstraint(
                fields=['tenant', 'chat_id'],
                name='uniq_telegram_link_tenant_chat'
            )
        ]

    def __str__(self):
        return f"{self.professional.email} -> Chat: {self.chat_id} (Proprio Bot: {'Sim' if self.bot_token else 'Não'})"
