from rest_framework import serializers
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.inventory.models import Product, Service

from .models import (
    Appointment,
    Charge,
    ChargeItem,
    ClinicalRecord,
    Encounter,
    FinalizeAudit,
)
from .state_utils import promote_overdue_scheduled_to_pending


class AppointmentSerializer(serializers.ModelSerializer):
    # Garante que 'professional' não seja exigido no POST e seja somente leitura
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    professional_name = serializers.SerializerMethodField(read_only=True)
    client_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "professional",
            "client",
            "professional_name",
            "client_name",
            "title",
            "visit_type",
            "start_at",
            "end_at",
            "location",
            "notes",
            "status",
            "finalized_at",
            "canceled_at",
            "whatsapp_confirmed",
            "created_device_id",
            "created_device_info",
            "ended_device_id",
            "ended_device_info",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "professional",
            "created_device_id",
            "created_device_info",
            "ended_device_id",
            "ended_device_info",
            "finalized_at",
            "canceled_at",
            "whatsapp_confirmed",
        ]

    # Semântica de tempos:
    # - end_at: término planejado OU real (se finalize antecipado encurta end_at = now).
    # - finalized_at: momento em que o profissional marcou como concluído (primeira vez; imutável).
    #   Pode ser > end_at quando a finalização ocorreu depois do horário planejado.
    #   Duração efetiva -> (end_at - start_at); atraso de registro -> max(0, finalized_at - end_at).

    def get_professional_name(self, obj):
        p = obj.professional
        if getattr(p, "id", None):
            return f"{p.first_name} {p.last_name}"
        return None

    def get_client_name(self, obj):
        c = obj.client
        if getattr(c, "id", None):
            return f"{c.first_name} {c.last_name}"
        return None

    def validate(self, attrs):
        start = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_at": "Fim deve ser após o início."})

        now = timezone.now()

        # Criação: não permitir agendamento no passado
        if self.instance is None and start and start < now:
            raise serializers.ValidationError({"start_at": "Não é permitido agendar no passado."})

        # Edição: permitir alterações com regras pontuais
        if self.instance is not None:
            inst_status = getattr(self.instance, "status", None)
            # Apenas compromissos ativos (scheduled) podem ser editados
            if inst_status and inst_status != Appointment.Status.SCHEDULED:
                raise serializers.ValidationError({
                    "detail": "Somente compromissos ativos podem ser editados."
                })
            # Status deve ser resolvido apenas via endpoints dedicados
            # (/finalize, /cancel, /done), nunca por PATCH generico.
            if "status" in attrs:
                new_status = attrs.get("status")
                if new_status is not None and new_status != inst_status:
                    raise serializers.ValidationError({
                        "status": "Use os endpoints dedicados para transição de status (finalize, cancel, done)."
                    })
            # Se o compromisso já está no passado, bloquear edições genéricas
            # Exceções permitidas:
            #  - encurtar end_at (sem mover início)
            inst_start = getattr(self.instance, 'start_at', None)
            inst_end = getattr(self.instance, 'end_at', None)
            if inst_start and inst_start < now:
                allowed = False
                # permitir apenas encurtar o fim (novo end <= atual end) e não mover início
                if 'end_at' in attrs and 'start_at' not in attrs:
                    try:
                        new_end = attrs.get('end_at')
                        if new_end is not None and inst_end is not None and new_end <= inst_end:
                            allowed = True
                    except Exception:
                        pass
                if not allowed:
                    raise serializers.ValidationError({
                        'detail': 'Edição de compromissos iniciados no passado não é permitida.'
                    })
            # Não permitir mover o início para o passado APENAS quando o campo start_at for explicitamente alterado.
            # Edits que não alteram start_at (por exemplo, encurtar end_at ou marcar como done) devem ser permitidos
            # mesmo se o compromisso já tiver iniciado no passado.
            if "start_at" in attrs:
                try:
                    new_start = attrs.get("start_at")
                    if new_start is not None and new_start < now:
                        raise serializers.ValidationError({
                            "start_at": "Não é permitido reagendar para o passado."
                        })
                except Exception:
                    # Se o start_at for inválido, deixe validações padrão tratarem adiante
                    pass

        # Cliente não pode ser alterado após criação do agendamento
        if self.instance is not None and "client" in attrs:
            if attrs["client"].id != self.instance.client.id:
                raise serializers.ValidationError({"client": "Cliente não pode ser alterado após criação."})

        # Tenta obter o profissional do payload; se ausente, usa o usuário autenticado
        professional = attrs.get("professional", getattr(self.instance, "professional", None))
        if professional is None:
            req = self.context.get("request") if hasattr(self, "context") else None
            user = getattr(req, "user", None) if req else None
            if getattr(user, "id", None):
                professional = user
        client = attrs.get("client", getattr(self.instance, "client", None))

        if client is not None and professional is not None:
            if getattr(client, "professional_id", None) != getattr(professional, "id", None):
                raise serializers.ValidationError(
                    {"client": "Cliente não pertence ao profissional autenticado."}
                )

        # Regra de transição: bloquear novo agendamento se o cliente possui compromisso pendente.
        # A regra oficial depende apenas de status persistido `pending`.
        if self.instance is None and client is not None:
            # Promoção oportunista para manter o estado persistido consistente no momento da criação.
            promote_overdue_scheduled_to_pending(
                Appointment.objects.filter(client=client, professional=professional)
            )
            pending_qs = Appointment.objects.filter(client=client, professional=professional).filter(
                status=Appointment.Status.PENDING
            )
            if pending_qs.exists():
                raise serializers.ValidationError({
                    "client": "Cliente possui compromisso pendente (não concluído/cancelado). Resolva o anterior antes de agendar um novo."
                })
        if professional and start and end:
            # conflito simples
            inst = self.instance if getattr(self, "instance", None) else None
            conflict = (
                Appointment.objects.filter(professional=professional)
                .exclude(
                    status__in=[
                        Appointment.Status.PENDING,
                        Appointment.Status.CANCELED,
                        Appointment.Status.DONE,
                    ]
                )
                .filter(Q(start_at__lt=end) & Q(end_at__gt=start))
            )
            if inst is not None:
                conflict = conflict.exclude(pk=inst.pk)
            if conflict.exists():
                raise serializers.ValidationError("Conflito de horário para o profissional.")

        return attrs


class FinalizeAuditSerializer(serializers.ModelSerializer):
    appointment_id = serializers.IntegerField(source="appointment.id", read_only=True)
    professional_id = serializers.IntegerField(source="professional.id", read_only=True)
    client_id = serializers.IntegerField(source="client.id", read_only=True)

    class Meta:
        model = FinalizeAudit
        fields = [
            "id",
            "appointment_id",
            "professional_id",
            "client_id",
            "device_id",
            "device_info",
            "client_now",
            "server_now",
            "drift_ms",
            "adjusted_times",
            "reason",
            "created_at",
        ]
        read_only_fields = fields


class EncounterSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    professional_name = serializers.SerializerMethodField(read_only=True)
    client_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Encounter
        fields = [
            "id",
            "professional",
            "professional_name",
            "client",
            "client_name",
            "appointment",
            "started_at",
            "ended_at",
            "chief_complaint",
            "assessment",
            "plan",
            "notes",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["professional", "professional_name", "client_name", "created_at", "updated_at"]

    def get_professional_name(self, obj):
        return f"{obj.professional.first_name} {obj.professional.last_name}".strip()

    def get_client_name(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}".strip()

    def validate(self, attrs):
        professional = getattr(self.context.get("request"), "user", None) or getattr(self.instance, "professional", None)
        client = attrs.get("client", getattr(self.instance, "client", None))
        appointment = attrs.get("appointment", getattr(self.instance, "appointment", None))
        started_at = attrs.get("started_at", getattr(self.instance, "started_at", timezone.now()))
        ended_at = attrs.get("ended_at", getattr(self.instance, "ended_at", None))
        chief_complaint = attrs.get("chief_complaint", getattr(self.instance, "chief_complaint", ""))
        assessment = attrs.get("assessment", getattr(self.instance, "assessment", ""))
        plan = attrs.get("plan", getattr(self.instance, "plan", ""))
        notes = attrs.get("notes", getattr(self.instance, "notes", ""))
        status = attrs.get("status", getattr(self.instance, "status", Encounter.Status.OPEN))

        instance = Encounter(
            professional=professional,
            client=client,
            appointment=appointment,
            started_at=started_at,
            ended_at=ended_at,
            chief_complaint=chief_complaint,
            assessment=assessment,
            plan=plan,
            notes=notes,
            status=status,
        )
        if self.instance:
            instance.pk = self.instance.pk
        instance.full_clean()
        return attrs


class ClinicalRecordSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    professional_name = serializers.SerializerMethodField(read_only=True)
    client_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ClinicalRecord
        fields = [
            "id",
            "professional",
            "professional_name",
            "client",
            "client_name",
            "encounter",
            "record_type",
            "title",
            "content",
            "recorded_at",
            "is_confidential",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["professional", "professional_name", "client_name", "created_at", "updated_at"]

    def get_professional_name(self, obj):
        return f"{obj.professional.first_name} {obj.professional.last_name}".strip()

    def get_client_name(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}".strip()

    def validate(self, attrs):
        professional = getattr(self.context.get("request"), "user", None) or getattr(self.instance, "professional", None)
        client = attrs.get("client", getattr(self.instance, "client", None))
        encounter = attrs.get("encounter", getattr(self.instance, "encounter", None))
        record_type = attrs.get("record_type", getattr(self.instance, "record_type", ClinicalRecord.RecordType.EVOLUTION))
        title = attrs.get("title", getattr(self.instance, "title", ""))
        content = attrs.get("content", getattr(self.instance, "content", ""))
        recorded_at = attrs.get("recorded_at", getattr(self.instance, "recorded_at", timezone.now()))
        is_confidential = attrs.get("is_confidential", getattr(self.instance, "is_confidential", False))

        instance = ClinicalRecord(
            professional=professional,
            client=client,
            encounter=encounter,
            record_type=record_type,
            title=title,
            content=content,
            recorded_at=recorded_at,
            is_confidential=is_confidential,
        )
        if self.instance:
            instance.pk = self.instance.pk
        instance.full_clean()
        return attrs


class ChargeItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    charge = serializers.IntegerField(source="charge_id", read_only=True)
    item_type = serializers.ChoiceField(choices=ChargeItem.ItemType.choices)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), allow_null=True, required=False)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), allow_null=True, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    sort_order = serializers.IntegerField(required=False, default=0)
    notes = serializers.CharField(required=False, allow_blank=True)
    paid = serializers.BooleanField(required=False, default=False)
    paid_at = serializers.DateTimeField(required=False, allow_null=True, default=None)


class ChargeSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    professional_name = serializers.SerializerMethodField(read_only=True)
    client_name = serializers.SerializerMethodField(read_only=True)
    items = ChargeItemSerializer(many=True)

    class Meta:
        model = Charge
        fields = [
            "id",
            "professional",
            "professional_name",
            "client",
            "client_name",
            "encounter",
            "appointment",
            "charge_type",
            "status",
            "title",
            "notes",
            "recipient_name",
            "recipient_phone",
            "currency",
            "total_amount",
            "shared_at",
            "paid_at",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "professional",
            "professional_name",
            "client_name",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def get_professional_name(self, obj):
        return f"{obj.professional.first_name} {obj.professional.last_name}".strip()

    def get_client_name(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}".strip()

    def validate(self, attrs):
        professional = getattr(self.context.get("request"), "user", None) or getattr(self.instance, "professional", None)
        client = attrs.get("client", getattr(self.instance, "client", None))
        encounter = attrs.get("encounter", getattr(self.instance, "encounter", None))
        appointment = attrs.get("appointment", getattr(self.instance, "appointment", None))
        charge_type = attrs.get("charge_type", getattr(self.instance, "charge_type", Charge.ChargeType.CHARGE))
        # Charge.status is the canonical state; item-level paid flags remain per-consultation annotations.
        status = attrs.get("status", getattr(self.instance, "status", Charge.Status.DRAFT))
        title = attrs.get("title", getattr(self.instance, "title", ""))
        notes = attrs.get("notes", getattr(self.instance, "notes", ""))
        recipient_name = attrs.get("recipient_name", getattr(self.instance, "recipient_name", ""))
        recipient_phone = attrs.get("recipient_phone", getattr(self.instance, "recipient_phone", ""))
        currency = attrs.get("currency", getattr(self.instance, "currency", "BRL"))
        shared_at = attrs.get("shared_at", getattr(self.instance, "shared_at", None))
        paid_at = attrs.get("paid_at", getattr(self.instance, "paid_at", None))

        instance = Charge(
            professional=professional,
            client=client,
            encounter=encounter,
            appointment=appointment,
            charge_type=charge_type,
            status=status,
            title=title,
            notes=notes,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            currency=currency,
            shared_at=shared_at,
            paid_at=paid_at,
        )
        if self.instance:
            instance.pk = self.instance.pk
            instance._state.adding = False  # prevent false unique-id error on PATCH
            instance.total_amount = self.instance.total_amount
        instance.full_clean()

        items = attrs.get("items")
        if self.instance and items is None:
            items = [
                {
                    "item_type": item.item_type,
                    "service": item.service,
                    "product": item.product,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "sort_order": item.sort_order,
                    "notes": item.notes,
                    "paid": item.paid,
                    "paid_at": item.paid_at,
                }
                for item in self.instance.items.all()
            ]

        if not items:
            raise serializers.ValidationError({"items": "Informe ao menos um item na cobrança."})

        for raw_item in items:
            item = ChargeItem(charge=instance, **raw_item)
            item.clean()

        return attrs

    def _save_items(self, charge, items_data):
        with transaction.atomic():
            charge.items.all().delete()
            for index, item_data in enumerate(items_data):
                payload = dict(item_data)
                payload.setdefault("sort_order", index)
                ChargeItem.objects.create(
                    charge=charge,
                    **payload,
                )
            charge.recalculate_total(save=True)
            charge.refresh_from_db()

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        charge = Charge.objects.create(**validated_data)
        self._save_items(charge, items_data)
        charge.refresh_from_db()
        return charge

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            self._save_items(instance, items_data)
            instance.refresh_from_db()
        return instance
