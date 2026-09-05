from django.db import models


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
