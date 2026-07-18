from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Appointment(models.Model):
    """Consulta/compromisso na agenda.

    Campos principais:
    - professional: Profissional dono da agenda (FK apps.register.Professional)
    - client: Cliente atendido (FK apps.register.Client)
    - title: Título curto exibido no card/agenda (ex.: "Retorno", "Avaliação")
    - visit_type: Tipo de consulta (enum simples: avaliacao, retorno, procedimento, outro)
    - start_at / end_at: Janela do agendamento (timezone-aware)
    - location: Texto opcional (endereço, sala)
    - notes: Observações do profissional
    - status: scheduled, pending, done, canceled
    - created_at/updated_at
    """

    class VisitType(models.TextChoices):
        AVALIACAO = "avaliacao", "Avaliação"
        RETORNO = "retorno", "Retorno"
        PROCEDIMENTO = "procedimento", "Procedimento"
        OUTRO = "outro", "Outro"
        CONSULTA = "consulta", "Consulta"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Agendado"
        ONGOING = "ongoing", "Em andamento"
        PENDING = "pending", "Pendente"
        DONE = "done", "Realizado"
        CANCELED = "canceled", "Cancelado"

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        "register.Professional",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="Profissional",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="Cliente",
    )

    title = models.CharField("Título", max_length=80)
    visit_type = models.CharField(
        "Tipo de consulta",
        max_length=20,
        choices=VisitType.choices,
        default=VisitType.CONSULTA,
    )

    start_at = models.DateTimeField("Início")
    end_at = models.DateTimeField("Fim")

    location = models.CharField("Local", max_length=120, blank=True)
    notes = models.TextField("Observações", blank=True)
    status = models.CharField(
        "Status", max_length=12, choices=Status.choices, default=Status.SCHEDULED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Timestamp real de conclusão (finalize) e de cancelamento
    # Mantidos separados para permitir auditoria distinta: quando finalizou vs quando cancelou.
    # Ambos opcionais; somente definidos na primeira ocorrência para preservar histórico.
    finalized_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Momento em que o compromisso foi marcado como concluído (primeira vez).",
    )
    canceled_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Momento em que o compromisso foi cancelado (primeira vez).",
    )

    # Dispositivo que criou e que finalizou (opcional)
    created_device_id = models.CharField(
        max_length=64, blank=True, null=True, help_text="Identificador do dispositivo que criou o compromisso"
    )
    created_device_info = models.TextField(blank=True, help_text="Informações técnicas do dispositivo (JSON) de criação")
    ended_device_id = models.CharField(
        max_length=64, blank=True, null=True, help_text="Identificador do dispositivo que finalizou o compromisso"
    )
    ended_device_info = models.TextField(blank=True, help_text="Informações técnicas do dispositivo (JSON) de finalização")

    # Push reminder tracking — True after the same-day reminder has been sent
    reminder_sent = models.BooleanField(
        default=False,
        help_text="True quando o lembrete push do dia já foi enviado para este agendamento.",
    )

    # WhatsApp confirmation tracking — True when professional opened WhatsApp to notify client
    whatsapp_confirmed = models.BooleanField(
        default=False,
        help_text="True quando o profissional abriu o WhatsApp para confirmar presença do cliente.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["professional", "start_at"]),
            models.Index(fields=["client", "start_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_device_id"]),
            models.Index(fields=["ended_device_id"]),
            models.Index(fields=["finalized_at"]),
            models.Index(fields=["canceled_at"]),
        ]
        ordering = ["start_at"]

    def clean(self):
        # validações simples
        if self.end_at <= self.start_at:
            raise ValidationError({"end_at": "Fim deve ser após o início."})
        # status cancelado não tem regra extra aqui; lógica adicional pode ir no viewset

    def overlaps(self):
        """Verifica se conflita com outro agendamento do mesmo profissional.
        Critério: [start, end) com mesmo profissional e status ainda programável.
        """
        qs = (
            Appointment.objects.filter(professional=self.professional)
            .exclude(pk=self.pk)
            .exclude(
                status__in=[
                    Appointment.Status.PENDING,
                    Appointment.Status.CANCELED,
                    Appointment.Status.DONE,
                ]
            )
            .filter(start_at__lt=self.end_at, end_at__gt=self.start_at)
        )
        return qs.exists()

    def __str__(self):
        when = timezone.localtime(self.start_at).strftime("%d/%m %H:%M") if self.start_at else "?"
        return f"{self.title} — {self.client} ({when})"


class FinalizeAudit(models.Model):
    """Auditoria de finalização de compromissos."""

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="finalize_audits"
    )
    professional = models.ForeignKey(
        "register.Professional", on_delete=models.CASCADE, related_name="finalize_audits"
    )
    client = models.ForeignKey(
        "clients.Client", on_delete=models.CASCADE, related_name="finalize_audits"
    )

    device_id = models.CharField(max_length=64, blank=True, null=True)
    device_info = models.TextField(blank=True)
    client_now = models.DateTimeField(blank=True, null=True)
    server_now = models.DateTimeField()
    drift_ms = models.IntegerField(blank=True, null=True)
    adjusted_times = models.BooleanField(default=False)
    reason = models.CharField(max_length=32, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["appointment", "created_at"]),
            models.Index(fields=["professional", "created_at"]),
            models.Index(fields=["client", "created_at"]),
            models.Index(fields=["device_id"]),
        ]
        ordering = ["-created_at"]


class Encounter(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Em andamento"
        CLOSED = "closed", "Encerrado"
        CANCELED = "canceled", "Cancelado"

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        "register.Professional",
        on_delete=models.CASCADE,
        related_name="encounters",
        verbose_name="Profissional",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="encounters",
        verbose_name="Cliente",
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.SET_NULL,
        related_name="clinical_encounter",
        null=True,
        blank=True,
        verbose_name="Agendamento",
    )
    started_at = models.DateTimeField("Início do atendimento", default=timezone.now)
    ended_at = models.DateTimeField("Fim do atendimento", null=True, blank=True)
    chief_complaint = models.CharField("Queixa principal", max_length=255, blank=True)
    assessment = models.TextField("Avaliação", blank=True)
    plan = models.TextField("Plano", blank=True)
    notes = models.TextField("Notas", blank=True)
    status = models.CharField(
        "Status",
        max_length=12,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["professional", "client", "status"]),
            models.Index(fields=["professional", "started_at"]),
            models.Index(fields=["client", "started_at"]),
        ]
        ordering = ["-started_at", "-id"]

    def clean(self):
        errors = {}

        if self.ended_at and self.started_at and self.ended_at < self.started_at:
            errors["ended_at"] = "Fim do atendimento deve ser após o início."

        if self.status == self.Status.OPEN and self.ended_at is not None:
            errors["ended_at"] = "Atendimentos abertos não podem ter horário de fim."

        if self.status in {self.Status.CLOSED, self.Status.CANCELED} and self.ended_at is None:
            errors["ended_at"] = "Informe o fim do atendimento ao encerrar ou cancelar."

        appointment = getattr(self, "appointment", None)
        professional_id = getattr(self, "professional_id", None)
        client_id = getattr(self, "client_id", None)

        if appointment is not None:
            if getattr(appointment, "professional_id", None) != professional_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo profissional."
            if getattr(appointment, "client_id", None) != client_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo cliente."

        open_qs = Encounter.objects.filter(
            professional_id=professional_id,
            client_id=client_id,
            status=self.Status.OPEN,
        )
        if self.pk:
            open_qs = open_qs.exclude(pk=self.pk)
        if self.status == self.Status.OPEN and open_qs.exists():
            errors["status"] = "Já existe um atendimento em andamento para este cliente."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Atendimento {self.client} — {self.status}"


class ClinicalRecord(models.Model):
    class RecordType(models.TextChoices):
        EVOLUTION = "evolution", "Evolução"
        ASSESSMENT = "assessment", "Avaliação"
        PLAN = "plan", "Plano"
        PRESCRIPTION = "prescription", "Prescrição"
        NOTE = "note", "Nota"

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        "register.Professional",
        on_delete=models.CASCADE,
        related_name="clinical_records",
        verbose_name="Profissional",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="clinical_records",
        verbose_name="Cliente",
    )
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.SET_NULL,
        related_name="records",
        null=True,
        blank=True,
        verbose_name="Atendimento",
    )
    record_type = models.CharField(
        "Tipo de registro",
        max_length=24,
        choices=RecordType.choices,
        default=RecordType.EVOLUTION,
    )
    title = models.CharField("Título", max_length=120, blank=True)
    content = models.TextField("Conteúdo")
    recorded_at = models.DateTimeField("Registrado em", default=timezone.now)
    is_confidential = models.BooleanField("Confidencial", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["professional", "client", "recorded_at"]),
            models.Index(fields=["client", "record_type", "recorded_at"]),
            models.Index(fields=["encounter", "recorded_at"]),
        ]
        ordering = ["-recorded_at", "-id"]

    def clean(self):
        errors = {}

        if not (self.content or "").strip():
            errors["content"] = "O registro clínico não pode ficar vazio."

        encounter = getattr(self, "encounter", None)
        professional_id = getattr(self, "professional_id", None)
        client_id = getattr(self, "client_id", None)

        if encounter is not None:
            if getattr(encounter, "professional_id", None) != professional_id:
                errors["encounter"] = "O atendimento precisa pertencer ao mesmo profissional."
            if getattr(encounter, "client_id", None) != client_id:
                errors["encounter"] = "O atendimento precisa pertencer ao mesmo cliente."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f"Prontuário {self.client} — {self.record_type}"


class Charge(models.Model):
    class ChargeType(models.TextChoices):
        QUOTE = "quote", "Orçamento"
        CHARGE = "charge", "Cobrança"

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        SENT = "sent", "Enviado"
        PAID = "paid", "Pago"
        CANCELED = "canceled", "Cancelado"

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(
        "register.Professional",
        on_delete=models.CASCADE,
        related_name="charges",
        verbose_name="Profissional",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="charges",
        verbose_name="Cliente",
    )
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.SET_NULL,
        related_name="charges",
        null=True,
        blank=True,
        verbose_name="Atendimento",
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        related_name="charges",
        null=True,
        blank=True,
        verbose_name="Agendamento",
    )
    charge_type = models.CharField(
        "Tipo",
        max_length=12,
        choices=ChargeType.choices,
        default=ChargeType.CHARGE,
    )
    status = models.CharField(
        "Status",
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    title = models.CharField("Título", max_length=120, blank=True)
    notes = models.TextField("Notas", blank=True)
    recipient_name = models.CharField("Nome do destinatário", max_length=160, blank=True)
    recipient_phone = models.CharField("Telefone do destinatário", max_length=32, blank=True)
    currency = models.CharField("Moeda", max_length=8, default="BRL")
    total_amount = models.DecimalField("Total", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    shared_at = models.DateTimeField("Compartilhado em", null=True, blank=True)
    paid_at = models.DateTimeField("Pago em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["professional", "client", "status"]),
            models.Index(fields=["appointment", "status"]),
            models.Index(fields=["encounter", "status"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at", "-id"]

    def clean(self):
        errors = {}

        encounter = getattr(self, "encounter", None)
        appointment = getattr(self, "appointment", None)
        professional_id = getattr(self, "professional_id", None)
        client_id = getattr(self, "client_id", None)

        if encounter is not None:
            if getattr(encounter, "professional_id", None) != professional_id:
                errors["encounter"] = "O atendimento precisa pertencer ao mesmo profissional."
            if getattr(encounter, "client_id", None) != client_id:
                errors["encounter"] = "O atendimento precisa pertencer ao mesmo cliente."

        if appointment is not None:
            if getattr(appointment, "professional_id", None) != professional_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo profissional."
            if getattr(appointment, "client_id", None) != client_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo cliente."

        encounter_appointment_id = getattr(encounter, "appointment_id", None)
        appointment_id = getattr(self, "appointment_id", None)
        if encounter is not None and appointment is not None and encounter_appointment_id:
            if encounter_appointment_id != appointment_id:
                errors["appointment"] = "Agendamento e atendimento precisam estar alinhados."

        if self.status == self.Status.CANCELED and self.paid_at is not None:
            errors["status"] = "Cobrança cancelada não pode ficar como paga."

        if errors:
            raise ValidationError(errors)

    def sync_status_fields(self):
        if self.status == self.Status.PAID:
            if self.paid_at is None:
                self.paid_at = timezone.now()
            return

        self.paid_at = None

    def save(self, *args, **kwargs):
        self.sync_status_fields()
        self.full_clean()
        return super().save(*args, **kwargs)

    def recalculate_total(self, save=True):
        total = Decimal("0.00")
        if self.pk:
            for item in ChargeItem.objects.filter(charge=self):
                total += item.line_total
        self.total_amount = total
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                total_amount=total,
                updated_at=timezone.now(),
            )
        return total

    def __str__(self):
        return self.title or f"{self.charge_type} — {self.client}"


class ChargeItem(models.Model):
    class ItemType(models.TextChoices):
        SERVICE = "service", "Serviço"
        PRODUCT = "product", "Produto"
        CUSTOM = "custom", "Personalizado"

    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    charge = models.ForeignKey(
        Charge,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Cobrança",
    )
    item_type = models.CharField(
        "Tipo de item",
        max_length=12,
        choices=ItemType.choices,
        default=ItemType.CUSTOM,
    )
    service = models.ForeignKey(
        "inventory.Service",
        on_delete=models.SET_NULL,
        related_name="charge_items",
        null=True,
        blank=True,
        verbose_name="Serviço",
    )
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.SET_NULL,
        related_name="charge_items",
        null=True,
        blank=True,
        verbose_name="Produto",
    )
    description = models.CharField("Descrição", max_length=255, blank=True)
    quantity = models.DecimalField("Quantidade", max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField("Preço unitário", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    paid = models.BooleanField("Pago", default=False)
    paid_at = models.DateTimeField("Pago em", null=True, blank=True)
    sort_order = models.PositiveIntegerField("Ordem", default=0)
    notes = models.CharField("Notas", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["charge", "sort_order"]),
            models.Index(fields=["item_type"]),
        ]
        ordering = ["sort_order", "id"]

    @property
    def line_total(self):
        return (self.quantity or Decimal("0")) * (self.unit_price or Decimal("0"))

    def clean(self):
        errors = {}

        if self.quantity <= 0:
            errors["quantity"] = "A quantidade deve ser maior que zero."

        if self.unit_price < 0:
            errors["unit_price"] = "O preço unitário não pode ser negativo."

        service = getattr(self, "service", None)
        product = getattr(self, "product", None)

        if self.item_type == self.ItemType.SERVICE:
            if service is None:
                errors["service"] = "Selecione um serviço para itens do tipo serviço."
            if product is not None:
                errors["product"] = "Itens de serviço não podem apontar para produto."
        elif self.item_type == self.ItemType.PRODUCT:
            if product is None:
                errors["product"] = "Selecione um produto para itens do tipo produto."
            if service is not None:
                errors["service"] = "Itens de produto não podem apontar para serviço."
        else:
            if service is not None or product is not None:
                errors["item_type"] = "Itens personalizados não podem referenciar serviço ou produto."
            if not (self.description or "").strip():
                errors["description"] = "Informe uma descrição para o item personalizado."

        if service is not None and getattr(service, "professional_id", None) != getattr(self.charge, "professional_id", None):
            errors["service"] = "O serviço precisa pertencer ao mesmo profissional da cobrança."

        if product is not None and getattr(product, "professional_id", None) != getattr(self.charge, "professional_id", None):
            errors["product"] = "O produto precisa pertencer ao mesmo profissional da cobrança."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service = getattr(self, "service", None)
        product = getattr(self, "product", None)
        if not self.description:
            if service is not None:
                self.description = service.name
            elif product is not None:
                self.description = product.name
        self.full_clean()
        result = super().save(*args, **kwargs)
        self.charge.recalculate_total(save=True)
        return result

    def delete(self, *args, **kwargs):
        charge = self.charge
        result = super().delete(*args, **kwargs)
        charge.recalculate_total(save=True)
        return result

    def __str__(self):
        return self.description or f"Item {self.pk}"
