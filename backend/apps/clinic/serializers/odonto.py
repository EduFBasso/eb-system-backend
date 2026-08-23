from django.db.models import Sum
from rest_framework import serializers

from apps.clinic.models.odonto import DentalProcedureContext, TreatmentPlan, TreatmentPlanItem


class DentalProcedureContextSerializer(serializers.ModelSerializer):
    scope = serializers.ChoiceField(
        choices=[
            ('tooth', 'Dente Específico'),
            ('arch', 'Arcada Inteira'),
            ('full', 'Arcada Superior e Inferior / Boca Toda'),
            ('full_arcade', 'Arcada Superior e Inferior'),
        ]
    )
    arcade_arch = serializers.ChoiceField(
        choices=[
            ('superior', 'Arcada Superior'),
            ('inferior', 'Arcada Inferior'),
            ('AMBAS', 'Arcada Superior e Inferior'),
        ],
        allow_null=True,
        required=False,
    )

    class Meta:
        model = DentalProcedureContext
        fields = ['id', 'scope', 'tooth_number', 'tooth_surface', 'arcade_arch', 'observations']

    def validate(self, attrs):
        scope = attrs.get('scope')
        arcade_arch = attrs.get('arcade_arch')

        # The combined arch is one anatomical context, never two item rows.
        if scope == 'full_arcade' or arcade_arch == 'AMBAS':
            attrs['scope'] = 'full'
            attrs['arcade_arch'] = None

        return attrs


class TreatmentPlanItemSerializer(serializers.ModelSerializer):
    dental_context = DentalProcedureContextSerializer(required=False, allow_null=True)
    service_name = serializers.CharField(
        source='service.name', read_only=True, allow_null=True
    )

    class Meta:
        model = TreatmentPlanItem
        fields = [
            'id',
            'plan',
            'kind',
            'service',
            'service_name',
            'product',
            'custom_name',
            'status',
            'patient_price',
            'started_at',
            'completed_at',
            'notes',
            'is_active',
            'external_item_id',
            'parent_item',
            'dental_context',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        context_data = validated_data.pop('dental_context', None)
        item = super().create(validated_data)
        if context_data:
            DentalProcedureContext.objects.create(item=item, **context_data)
        return item

    def update(self, instance, validated_data):
        context_data = validated_data.pop('dental_context', None)
        instance = super().update(instance, validated_data)
        if context_data is not None:
            DentalProcedureContext.objects.update_or_create(
                item=instance, defaults=context_data
            )
        return instance


class TreatmentPlanListSerializer(serializers.ModelSerializer):
    pending_items = serializers.SerializerMethodField()
    completed_items = serializers.SerializerMethodField()
    plan_total = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentPlan
        fields = [
            'id',
            'client',
            'name',
            'status',
            'started_at',
            'completed_at',
            'payment_condition',
            'installments_count',
            'first_due_date',
            'notes',
            'external_treatment_id',
            'pending_items',
            'completed_items',
            'plan_total',
            'is_printed',
            'printed_at',
            'created_at',
            'updated_at',
        ]

    def get_pending_items(self, obj: TreatmentPlan) -> int:
        return obj.items.filter(status=TreatmentPlanItem.Status.PENDING, is_active=True).count()  # type: ignore[attr-defined]

    def get_completed_items(self, obj: TreatmentPlan) -> int:
        return obj.items.filter(status=TreatmentPlanItem.Status.COMPLETED).count()  # type: ignore[attr-defined]

    def get_plan_total(self, obj: TreatmentPlan):
        result = obj.items.filter(is_active=True).aggregate(total=Sum('patient_price'))  # type: ignore[attr-defined]
        return f"{result['total'] or 0:.2f}"


class TreatmentPlanDetailSerializer(serializers.ModelSerializer):
    items = TreatmentPlanItemSerializer(many=True, read_only=True)

    class Meta:
        model = TreatmentPlan
        fields = [
            'id',
            'client',
            'name',
            'status',
            'started_at',
            'completed_at',
            'payment_condition',
            'installments_count',
            'first_due_date',
            'notes',
            'external_treatment_id',
            'is_printed',
            'printed_at',
            'items',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'items']


class TreatmentPlanWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TreatmentPlan
        fields = [
            'id',
            'client',
            'name',
            'status',
            'started_at',
            'completed_at',
            'payment_condition',
            'installments_count',
            'first_due_date',
            'notes',
            'external_treatment_id',
            'is_printed',
            'printed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_printed']

    def validate(self, attrs):
        condition = attrs.get(
            'payment_condition',
            getattr(self.instance, 'payment_condition', TreatmentPlan.PaymentCondition.CASH),
        )
        installments = attrs.get(
            'installments_count',
            getattr(self.instance, 'installments_count', 2),
        )
        if condition == TreatmentPlan.PaymentCondition.INSTALLMENTS and installments < 2:
            raise serializers.ValidationError(
                {'installments_count': 'Informe pelo menos 2 parcelas.'}
            )
        return attrs
