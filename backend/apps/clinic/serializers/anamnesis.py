from rest_framework import serializers
from apps.clinic.models.anamnesis import AnamnesisField, AnamnesisResponse, AnamneseBase, AnamneseOdontologia
from apps.clinic.models.clients import Client


class AnamnesisFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnamnesisField
        fields = [
            'id', 'code', 'sector', 'sector_order', 'label',
            'field_type', 'selection_mode', 'options', 'placeholder', 'depends_on',
            'show_when_value', 'order', 'is_active',
        ]
        read_only_fields = ['id']


class AnamnesisResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnamnesisResponse
        fields = [
            'id', 'client', 'field', 'field_label_snap',
            'value', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def create(self, validated_data):
        # Auto-fill field_label_snap from the field if not provided
        field = validated_data.get('field')
        if field and not validated_data.get('field_label_snap'):
            validated_data['field_label_snap'] = field.label
        return super().create(validated_data)


class AnamnesisResponseBulkItemSerializer(serializers.Serializer):
    """Single item in a bulk upsert payload."""
    field = serializers.PrimaryKeyRelatedField(queryset=AnamnesisField.objects.all())
    value = serializers.CharField(allow_blank=True, default='')

    def validate_field(self, value):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and value.professional_id != user.id:
            raise serializers.ValidationError(
                'Campo de anamnese não pertence ao profissional autenticado.',
            )
        return value


class AnamnesisResponseBulkSerializer(serializers.Serializer):
    """
    Payload for POST /anamnesis/responses/bulk_save/
    { "client": 5, "responses": [{"field": 1, "value": "Sim"}, ...] }
    """
    client = serializers.IntegerField()
    responses = AnamnesisResponseBulkItemSerializer(many=True)


class DentalAnamnesisSerializer(serializers.ModelSerializer):
    """
    [SOLID - Single Responsibility Principle]
    Handles payload incoming from the frontend React MUI form,
    atomically routing data into AnamneseBase and AnamneseOdontologia.
    """
    client_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = AnamneseOdontologia
        fields = [
            'client_id',
            'gum_bleeding',
            'floss_usage',
            'bruxism_clenching',
            'tooth_brushing_frequency',
            'chief_dental_complaint'
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Autenticação necessária.")
            
        # Extracts tenant context through active user membership
        membership = request.user.tenant_memberships.filter(is_active=True).first()
        if not membership:
            raise serializers.ValidationError("Profissional não possui vínculo ativo com nenhuma clínica.")
        tenant = membership.tenant
        
        # Professional profile resolution — request.user IS the professional in this system
        professional = request.user
        
        client_id = validated_data.pop('client_id')
        try:
            client = Client.objects.get(id=client_id, tenant=tenant)
        except Client.DoesNotExist:
            raise serializers.ValidationError({"client_id": "Cliente não localizado ou pertence a outra clínica."})

        # 1. Upsert universal header record (AnamneseBase)
        anamnese_base, _ = AnamneseBase.objects.get_or_create(
            client=client,
            tenant=tenant,
            defaults={'professional': professional}
        )

        # 2. Upsert specialized dental payload (AnamneseOdontologia)
        anamnese_odonto, _ = AnamneseOdontologia.objects.update_or_create(
            anamnese_base=anamnese_base,
            defaults={
                **validated_data,
                'professional': professional
            }
        )
        return anamnese_odonto