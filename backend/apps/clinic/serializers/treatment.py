from django.db.models import Sum
from rest_framework import serializers

from apps.clinic.models.treatment import TreatmentPlan, TreatmentPlanItem
from apps.clinic.models.odonto import DentalProcedureContext
from apps.clinic.models.podologia import PodologyProcedureContext
from apps.clinic.serializers.odonto import DentalProcedureContextSerializer
from apps.clinic.serializers.podologia import PodologyProcedureContextSerializer


class TreatmentPlanItemSerializer(serializers.ModelSerializer):
    """Serializer neutro do item de plano — cada especialidade agrega seu contexto
    anatômico opcional (dental_context, podology_context, ...) sem duplicar esta classe."""
    dental_context = DentalProcedureContextSerializer(required=False, allow_null=True)
    podology_context = PodologyProcedureContextSerializer(required=False, allow_null=True)
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
            'podology_context',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        dental_data = attrs.get('dental_context')
        podology_data = attrs.get('podology_context')
        if dental_data and podology_data:
            raise serializers.ValidationError(
                'Um item não pode ter contexto odontológico e de podologia ao mesmo tempo.'
            )
        plan = attrs.get('plan') or getattr(self.instance, 'plan', None)
        tenant = plan.tenant if plan else None
        if dental_data and tenant and not tenant.has_capability('odonto'):
            raise serializers.ValidationError(
                {'dental_context': 'O tenant não possui a capability "odonto" habilitada.'}
            )
        if podology_data and tenant and not tenant.has_capability('podologia'):
            raise serializers.ValidationError(
                {'podology_context': 'O tenant não possui a capability "podologia" habilitada.'}
            )
        return attrs

    def create(self, validated_data):
        dental_data = validated_data.pop('dental_context', None)
        podology_data = validated_data.pop('podology_context', None)
        item = super().create(validated_data)
        if dental_data:
            DentalProcedureContext.objects.create(item=item, **dental_data)
        if podology_data:
            PodologyProcedureContext.objects.create(
                treatment_plan_item=item,
                tenant=item.plan.tenant,
                **podology_data,
            )
        return item

    def update(self, instance, validated_data):
        dental_data = validated_data.pop('dental_context', None)
        podology_data = validated_data.pop('podology_context', None)
        instance = super().update(instance, validated_data)
        if dental_data is not None:
            DentalProcedureContext.objects.update_or_create(
                item=instance, defaults=dental_data
            )
        if podology_data is not None:
            PodologyProcedureContext.objects.update_or_create(
                treatment_plan_item=instance,
                defaults={'tenant': instance.plan.tenant, **podology_data},
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
