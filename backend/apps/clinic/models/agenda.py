from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Appointment(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela o compromisso/reserva de horário na agenda da clínica.
    Sua única responsabilidade é gerenciar o tempo, o profissional escalado 
    e o cliente que solicitou a vaga.
    """

    class VisitType(models.TextChoices):
        """Simplificação das opções para otimizar o dia a dia da clínica."""
        CONSULTA = "consulta", "Consulta (Primeira vez / Queixa nova)"
        RETORNO = "retorno", "Retorno (Acompanhamento)"
        OUTRO = "outro", "Outro compromisso (Bloqueio / Reunião)"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Agendado"
        PENDING = "pending", "Pendente de Fechamento"  # Útil para a trava de auditoria automática
        DONE = "done", "Realizado"
        CANCELED = "canceled", "Cancelado"

    # [Garantia Arquitetural] O agendamento DEVE pertencer a uma clínica (Tenant) obrigatoriamente
    tenant = models.ForeignKey(
        'authentication.Tenant', 
        on_delete=models.CASCADE, 
        null=False, 
        blank=False,
        verbose_name="Clínica/Tenant"
    )
    
    professional = models.ForeignKey(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="Profissional",
    )
    
    # O cliente agora se vincula normalmente via chave estrangeira direta
    client = models.ForeignKey(
        "clinic.Client",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="Cliente",
    )

    title = models.CharField("Título/Motivo", max_length=80)
    visit_type = models.CharField(
        "Tipo de consulta",
        max_length=20,
        choices=VisitType.choices,
        default=VisitType.CONSULTA,
    )

    start_at = models.DateTimeField("Início do Atendimento")
    end_at = models.DateTimeField("Fim do Atendimento")

    location = models.CharField("Local/Sala", max_length=120, blank=True)
    notes = models.TextField("Observações da Agenda", blank=True)
    status = models.CharField(
        "Status", max_length=12, choices=Status.choices, default=Status.SCHEDULED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    canceled_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Momento em que o compromisso foi cancelado.",
    )

    created_device_id = models.CharField(
        max_length=64, blank=True, null=True, help_text="ID do dispositivo que criou"
    )
    created_device_info = models.TextField(blank=True, help_text="Metadata técnica do dispositivo (JSON) na criação")

    # Controle de Mensagens (Telegram push e Confirmação de abertura de link)
    reminder_sent = models.BooleanField(
        default=False,
        help_text="True quando o sistema já disparou o push/lembrete do dia.",
    )
    whatsapp_confirmed = models.BooleanField(
        default=False,
        help_text="True quando o profissional acionou a rotina de envio para o cliente.",
    )

    class Meta:
        app_label = 'clinic'
        indexes = [
            models.Index(fields=["tenant", "professional", "start_at"]),
            models.Index(fields=["tenant", "client", "start_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["canceled_at"]),
        ]
        ordering = ["start_at"]
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"

    def clean(self):
        """Garante consistência cronológica mínima antes de salvar no banco."""
        if self.start_at and self.end_at:
            if self.end_at <= self.start_at:
                raise ValidationError({"end_at": "O horário de término deve ser posterior ao horário de início."})

    def overlaps(self):
        """
        Verifica conflitos de horários na agenda do profissional.
        Garante que [start, end) não intercepte outro agendamento ativo na mesma clínica.
        """
        qs = (
            Appointment.objects.filter(tenant=self.tenant, professional=self.professional)
            .exclude(pk=self.pk)
            .exclude(status=Appointment.Status.CANCELED)  # Cancelados liberam a agenda imediatamente
            .filter(start_at__lt=self.end_at, end_at__gt=self.start_at)
        )
        return qs.exists()

    def __str__(self):
        when = timezone.localtime(self.start_at).strftime("%d/%m %H:%M") if self.start_at else "?"
        return f"{self.title} — {self.client} ({when})"

class Encounter(models.Model):
    """
    Início do bloco de Prontuário / Sessão de Atendimento Clínico real.
    """
    class Status(models.TextChoices):
        OPEN = "open", "Sessão Aberta / Em Andamento"
        CLOSED = "closed", "Sessão Encerrada"
        CANCELED = "canceled", "Sessão Cancelada"

    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    professional = models.ForeignKey(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="encounters",
        verbose_name="Profissional",
    )
    client = models.ForeignKey(
        "clinic.Client",
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
        verbose_name="Agendamento Relacionado",
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
        app_label = 'clinic'
        indexes = [
            models.Index(fields=["tenant", "professional", "client", "status"]),
            models.Index(fields=["tenant", "professional", "started_at"]),
            models.Index(fields=["tenant", "client", "started_at"]),
        ]
        ordering = ["-started_at", "-id"]
        verbose_name = "Sessão de Atendimento"
        verbose_name_plural = "Sessões de Atendimentos"

    def clean(self):
        """
        [SOLID - Single Responsibility] 
        Valida regras estritas de consistência médica e integridade de dados (Multi-tenant).
        """
        errors = {}

        # 1. Validações de Tempo
        if self.ended_at and self.started_at and self.ended_at < self.started_at:
            errors["ended_at"] = "O horário de término não pode ser anterior ao início."

        if self.status == self.Status.OPEN and self.ended_at is not None:
            errors["ended_at"] = "Atendimentos em andamento não podem ter horário de término registrado."

        if self.status in {self.Status.CLOSED, self.Status.CANCELED} and self.ended_at is None:
            errors["ended_at"] = "Informe obrigatoriamente o horário de encerramento/cancelamento."

        # 2. Validações de Vinculações Cruzadas (Segurança)
        appointment = getattr(self, "appointment", None)
        professional_id = getattr(self, "professional_id", None)
        client_id = getattr(self, "client_id", None)
        tenant_id = getattr(self, "tenant_id", None)

        if appointment is not None:
            if getattr(appointment, "tenant_id", None) != tenant_id:
                errors["appointment"] = "O agendamento pertence a outra unidade/clínica (Tenant inválido)."
            if getattr(appointment, "professional_id", None) != professional_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo profissional deste atendimento."
            if getattr(appointment, "client_id", None) != client_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo cliente deste atendimento."

        # 3. Trava de Segurança Contra Sessões Duplicadas Simultâneas
        open_qs = Encounter.objects.filter(
            tenant_id=tenant_id,
            professional_id=professional_id,
            client_id=client_id,
            status=self.Status.OPEN,
        )
        if self.pk:
            open_qs = open_qs.exclude(pk=self.pk)
            
        if self.status == self.Status.OPEN and open_qs.exists():
            errors["status"] = "Já existe uma sessão de atendimento aberta para este cliente com este profissional."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Obriga o Django a executar a função clean() antes de persistir os dados
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Sessão {self.client} — {self.status}"


class ClinicalRecord(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Guarda uma entrada/evolução histórica no prontuário do cliente.
    Uma sessão (Encounter) pode gerar múltiplas notas/prescrições independentes.
    """
    class RecordType(models.TextChoices):
        EVOLUTION = "evolution", "Evolução"
        ASSESSMENT = "assessment", "Avaliação"
        PLAN = "plan", "Plano"
        PRESCRIPTION = "prescription", "Prescrição"
        NOTE = "note", "Nota / Anotação"

    # [Multi-tenant] Prontuário trancado estritamente dentro de sua respectiva clínica
    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    
    professional = models.ForeignKey(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="clinical_records",
        verbose_name="Profissional",
    )
    client = models.ForeignKey(
        "clinic.Client",
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
        verbose_name="Atendimento Clínico",
    )
    record_type = models.CharField(
        "Tipo de registro",
        max_length=24,
        choices=RecordType.choices,
        default=RecordType.EVOLUTION,
    )
    title = models.CharField("Título da Nota", max_length=120, blank=True)
    content = models.TextField("Conteúdo Clínico / Relato")
    recorded_at = models.DateTimeField("Registrado em", default=timezone.now)
    is_confidential = models.BooleanField("Confidencial (Apenas o próprio profissional visualiza)", default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        indexes = [
            models.Index(fields=["tenant", "professional", "client", "recorded_at"]),
            models.Index(fields=["tenant", "client", "record_type", "recorded_at"]),
        ]
        ordering = ["-recorded_at", "-id"]
        verbose_name = "Registro de Prontuário"
        verbose_name_plural = "Registros de Prontuários"

    def clean(self):
        errors = {}

        if not (self.content or "").strip():
            errors["content"] = "O texto do registro clínico não pode ser salvo em branco."

        encounter = getattr(self, "encounter", None)
        professional_id = getattr(self, "professional_id", None)
        client_id = getattr(self, "client_id", None)
        tenant_id = getattr(self, "tenant_id", None)

        if encounter is not None:
            if getattr(encounter, "tenant_id", None) != tenant_id:
                errors["encounter"] = "O atendimento clínico pertence a outra clínica."
            if getattr(encounter, "professional_id", None) != professional_id:
                errors["encounter"] = "O prontuário deve ser assinado pelo mesmo profissional da sessão aberta."
            if getattr(encounter, "client_id", None) != client_id:
                errors["encounter"] = "O prontuário deve pertencer ao mesmo cliente em atendimento."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f"Prontuário {self.client} — {self.record_type}"


class Charge(models.Model):
    """
    [SOLID - Interface Segregation] 
    Modela a camada financeira simplificada atrelada à clínica. 
    Permite emitir orçamentos ou cobranças direto da sessão de atendimento.
    """
    class ChargeType(models.TextChoices):
        QUOTE = "quote", "Orçamento"
        CHARGE = "charge", "Cobrança Efetiva"

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        SENT = "sent", "Enviado ao Cliente"
        PAID = "paid", "Pago / Liquidado"
        CANCELED = "canceled", "Cancelado"

    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    
    professional = models.ForeignKey(
        "authentication.Professional",
        on_delete=models.CASCADE,
        related_name="charges",
        verbose_name="Profissional Responsável",
    )
    client = models.ForeignKey(
        "clinic.Client",
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
        verbose_name="Sessão Geradora",
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        related_name="charges",
        null=True,
        blank=True,
        verbose_name="Agendamento Gerador",
    )
    charge_type = models.CharField(
        "Tipo Financeiro",
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
    title = models.CharField("Título / Descritivo Curto", max_length=120, blank=True)
    notes = models.TextField("Observações Financeiras / Termos", blank=True)
    recipient_name = models.CharField("Nome do Destinatário (Se diferente do Cliente)", max_length=160, blank=True)
    recipient_phone = models.CharField("Telefone para Envio", max_length=32, blank=True)
    currency = models.CharField("Moeda", max_length=8, default="BRL")
    
    # Campo monetário de alta precisão
    total_amount = models.DecimalField("Valor Total (R$)", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    
    shared_at = models.DateTimeField("Compartilhado em", null=True, blank=True)
    paid_at = models.DateTimeField("Pago em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        indexes = [
            models.Index(fields=["tenant", "professional", "client", "status"]),
            models.Index(fields=["tenant", "appointment", "status"]),
            models.Index(fields=["tenant", "encounter", "status"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at", "-id"]
        verbose_name = "Cobrança / Orçamento"
        verbose_name_plural = "Cobranças & Orçamentos"

    def clean(self):
        """
        [SOLID - Single Responsibility]
        Valida a consistência cruzada entre agendamento, atendimento e regras fiscais básicas.
        """
        errors = {}
        
        encounter = getattr(self, "encounter", None)
        appointment = getattr(self, "appointment", None)
        professional_id = getattr(self, "professional_id", None)
        client_id = getattr(self, "client_id", None)
        tenant_id = getattr(self, "tenant_id", None)

        # 1. Validações de Integridade do Atendimento
        if encounter is not None:
            if getattr(encounter, "tenant_id", None) != tenant_id:
                errors["encounter"] = "O atendimento clínico indicado pertence a outra clínica."
            if getattr(encounter, "professional_id", None) != professional_id:
                errors["encounter"] = "O atendimento precisa pertencer ao mesmo profissional desta cobrança."
            if getattr(encounter, "client_id", None) != client_id:
                errors["encounter"] = "O atendimento precisa pertencer ao mesmo cliente."

        # 2. Validações de Integridade do Agendamento
        if appointment is not None:
            if getattr(appointment, "tenant_id", None) != tenant_id:
                errors["appointment"] = "O agendamento indicado pertence a outra clínica."
            if getattr(appointment, "professional_id", None) != professional_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo profissional."
            if getattr(appointment, "client_id", None) != client_id:
                errors["appointment"] = "O agendamento precisa pertencer ao mesmo cliente."

        # 3. Alinhamento entre Agendamento e Atendimento
        encounter_appointment_id = getattr(encounter, "appointment_id", None)
        appointment_id = getattr(self, "appointment_id", None)
        if encounter is not None and appointment is not None and encounter_appointment_id:
            if encounter_appointment_id != appointment_id:
                errors["appointment"] = "O agendamento e o atendimento clínico indicados estão desalinhados."

        # 4. Regra de Negócio Comercial
        if self.status == self.Status.CANCELED and self.paid_at is not None:
            errors["status"] = "Uma cobrança cancelada não pode conter data de pagamento ativa."

        if errors:
            raise ValidationError(errors)

    def sync_status_fields(self):
        """Automação de data de recebimento conforme o status financeiro."""
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
        """
        Recalcula dinamicamente a soma dos itens acoplados.
        Utiliza o update direto caso já persistido para evitar loops de save.
        """
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
    """
    [SOLID - Single Responsibility Principle]
    Representa uma linha específica da cobrança. Pode conter um Produto do estoque,
    um Serviço prestado pela clínica ou um lançamento Personalizado manual.
    """
    class ItemType(models.TextChoices):
        SERVICE = "service", "Serviço"
        PRODUCT = "product", "Produto"
        CUSTOM = "custom", "Lançamento Personalizado"

    # [Multi-tenant] Item de venda rigorosamente atrelado à empresa controladora
    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, null=False, blank=False)
    
    charge = models.ForeignKey(
        Charge,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Cobrança Mãe",
    )
    item_type = models.CharField(
        "Tipo de item",
        max_length=12,
        choices=ItemType.choices,
        default=ItemType.CUSTOM,
    )
    service = models.ForeignKey(
        "clinic.Service",
        on_delete=models.SET_NULL,
        related_name="charge_items",
        null=True,
        blank=True,
        verbose_name="Serviço",
    )
    product = models.ForeignKey(
        "clinic.Product",
        on_delete=models.SET_NULL,
        related_name="charge_items",
        null=True,
        blank=True,
        verbose_name="Produto",
    )
    
    description = models.CharField("Descrição do Item", max_length=255, blank=True)
    quantity = models.DecimalField("Quantidade", max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField("Preço Unitário (R$)", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    
    # Rastreabilidade individual de itens pagos (útil para orçamentos parciais)
    paid = models.BooleanField("Item Pago?", default=False)
    paid_at = models.DateTimeField("Pago em", null=True, blank=True)
    
    sort_order = models.PositiveIntegerField("Ordem de Exibição", default=0)
    notes = models.CharField("Notas Internas do Item", max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'clinic'
        indexes = [
            models.Index(fields=["tenant", "charge", "sort_order"]),
            models.Index(fields=["item_type"]),
        ]
        ordering = ["sort_order", "id"]
        verbose_name = "Item de Cobrança"
        verbose_name_plural = "Itens de Cobrança"

    @property
    def line_total(self):
        """Calcula o valor total desta linha (Quantidade x Preço Unitário)."""
        return (self.quantity or Decimal("0")) * (self.unit_price or Decimal("0"))

    def clean(self):
        """Valida a integridade lógica e comercial dos itens lançados."""
        errors = {}

        if self.quantity <= 0:
            errors["quantity"] = "A quantidade deve ser estritamente maior que zero."

        if self.unit_price < 0:
            errors["unit_price"] = "O preço unitário não pode conter valores negativos."

        service = getattr(self, "service", None)
        product = getattr(self, "product", None)
        tenant_id = getattr(self, "tenant_id", None)

        # Validação Multi-tenant de segurança do estoque/catálogo
        if service is not None and getattr(service, "tenant_id", None) != tenant_id:
            errors["service"] = "Este serviço pertence a outra unidade/clínica."
            
        if product is not None and getattr(product, "tenant_id", None) != tenant_id:
            errors["product"] = "Este produto pertence a outra unidade/clínica."

        # Validações estritas baseadas no tipo de item selecionado
        if self.item_type == self.ItemType.SERVICE:
            if service is None:
                errors["service"] = "Por favor, indique o serviço para este item."
            if product is not None:
                errors["product"] = "Itens categorizados como serviço não podem referenciar produtos."
                
        elif self.item_type == self.ItemType.PRODUCT:
            if product is None:
                errors["product"] = "Por favor, indique o produto para este item."
            if service is not None:
                errors["service"] = "Itens categorizados como produto não podem referenciar serviços."
                
        else:  # Customizado
            if service is not None or product is not None:
                errors["item_type"] = "Lançamentos personalizados não devem fazer referência a serviços ou produtos cadastrados."
            if not (self.description or "").strip():
                errors["description"] = "A descrição é obrigatória para lançamentos personalizados."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Garante o preenchimento automático do descritivo e atualiza o total da nota."""
        service = getattr(self, "service", None)
        product = getattr(self, "product", None)
        
        # Fallback de descrição inteligente baseado no catálogo
        if not self.description:
            if service is not None:
                self.description = service.name
            elif product is not None:
                self.description = product.name
                
        self.full_clean()
        result = super().save(*args, **kwargs)
        
        # Dispara o recálculo do total na cobrança agregadora
        self.charge.recalculate_total(save=True)
        return result

    def delete(self, *args, **kwargs):
        """Ao deletar um item, abate o valor imediatamente na cobrança mãe."""
        charge = self.charge
        result = super().delete(*args, **kwargs)
        charge.recalculate_total(save=True)
        return result

    def __str__(self):
        return self.description or f"Item {self.pk}"
