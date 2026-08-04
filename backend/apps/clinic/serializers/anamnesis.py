from rest_framework import serializers
from .models import AnamnesisField, AnamnesisResponse


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
