from django.db import models


class TelegramProfessionalLink(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela as credenciais e o canal de comunicação do Telegram de um Profissional.
    Permite que cada profissional configure o token do seu próprio Bot (BotFather)
    para interagir de forma isolada e privada com seus respectivos clientes.
    """
    # [Garantia Multi-tenant] Vincula o canal de comunicação à clínica
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
        app_label = 'clinic'
        verbose_name = "Reminders - Vínculo Telegram"
        verbose_name_plural = "Reminders - Vínculos Telegram"
        
        constraints = [
            # Garante que um mesmo ID de chat não seja duplicado dentro da mesma clínica
            models.UniqueConstraint(
                fields=['tenant', 'chat_id'],
                name='uniq_telegram_link_tenant_chat'
            )
        ]

    def __str__(self):
        return f"{self.professional.user.email} -> Chat: {self.chat_id} (Proprio Bot: {'Sim' if self.bot_token else 'Não'})"


class ReminderDelivery(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Tabela de auditoria estrita e imutável para registrar o histórico e o payload
    exato de cada tentativa de envio de lembrete realizada pelo sistema.
    """
    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"

    class Status(models.TextChoices):
        SENT = "sent", "Enviado com Sucesso"
        FAILED = "failed", "Falhou"
        SKIPPED = "skipped", "Ignorado / Cancelado pelo Sistema"

    tenant = models.ForeignKey(
        'authentication.Tenant', 
        on_delete=models.CASCADE, 
        null=False, 
        blank=False,
        verbose_name="Clínica/Tenant"
    )

    appointment = models.ForeignKey(
        "clinic.Appointment",
        on_delete=models.CASCADE,
        related_name="reminder_deliveries",
        verbose_name="Agendamento Relacionado"
    )
    professional = models.ForeignKey(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="reminder_deliveries",
        verbose_name="Profissional Solicitante"
    )
    channel = models.CharField(
        "Canal de Envio",
        max_length=16,
        choices=Channel.choices,
        default=Channel.TELEGRAM,
    )
    status = models.CharField("Estado do Envio", max_length=16, choices=Status.choices)
    attempted_at = models.DateTimeField("Tentativa em", auto_now_add=True)
    sent_at = models.DateTimeField("Enviado Efetivamente em", blank=True, null=True)
    error_message = models.TextField("Mensagem de Erro da API", blank=True)
    
    # Histórico dos dados para auditoria jurídica e técnica de entrega
    payload = models.JSONField("Dados Enviados (JSON)", default=dict, blank=True)
    response_payload = models.JSONField("Resposta da API (JSON)", default=dict, blank=True)
    external_message_id = models.CharField("ID da Mensagem no Servidor Externo", max_length=64, blank=True)

    class Meta:
        app_label = 'clinic'
        verbose_name = "Reminders - Log de Entrega"
        verbose_name_plural = "Reminders - Logs de Entregas"
        indexes = [
            models.Index(fields=["tenant", "professional", "attempted_at"]),
            models.Index(fields=["tenant", "appointment", "channel"]),
            models.Index(fields=["tenant", "status", "attempted_at"]),
        ]

    def __str__(self):
        return f"Envio #{self.id} — Agendamento: {self.appointment_id} ({self.status})"
