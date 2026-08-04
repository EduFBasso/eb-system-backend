from django.db import models


class TelegramProfessionalLink(models.Model):
    professional = models.OneToOneField(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="telegram_link",
        verbose_name="Profissional",
    )
    chat_id = models.CharField(max_length=64, unique=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Vínculo Telegram"
        verbose_name_plural = "Vínculos Telegram"

    def __str__(self):
        return f"{self.professional.email} -> {self.chat_id}"


class ReminderDelivery(models.Model):
    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"

    class Status(models.TextChoices):
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falhou"
        SKIPPED = "skipped", "Ignorado"

    appointment = models.ForeignKey(
        "clinic.Appointment",
        on_delete=models.CASCADE,
        related_name="reminder_deliveries",
    )
    professional = models.ForeignKey(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="reminder_deliveries",
    )
    channel = models.CharField(
        max_length=16,
        choices=Channel.choices,
        default=Channel.TELEGRAM,
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    attempted_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    external_message_id = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = "Entrega de lembrete"
        verbose_name_plural = "Entregas de lembretes"
        indexes = [
            models.Index(fields=["professional", "attempted_at"]),
            models.Index(fields=["appointment", "channel"]),
            models.Index(fields=["status", "attempted_at"]),
        ]

    def __str__(self):
        return f"{self.appointment_id} / {self.channel} / {self.status}"  # type: ignore[attr-defined]