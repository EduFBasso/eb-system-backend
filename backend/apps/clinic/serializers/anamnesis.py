from rest_framework import serializers
from apps.clinic.models.anamnesis import AnamneseBase, AnamneseOdontologia
from apps.clinic.models.clients import Client
from apps.authentication.services.permissions import get_active_tenant_membership


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
        membership = get_active_tenant_membership(
            request.user,
            ecosystem='clinic',
        )
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