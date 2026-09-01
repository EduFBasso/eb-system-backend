from rest_framework import serializers
from apps.clinic.models.treatment import TreatmentPlanItem
from apps.clinic.models.podologia import PodologyProcedureContext

class PodologyProcedureContextSerializer(serializers.ModelSerializer):
    """
    Serializa os dados anatômicos dos Pés e Mãos para o Frontend (React).
    """
    class Meta:
        model = PodologyProcedureContext
        fields = ['id', 'scope', 'location_number']

class PodologyTreatmentPlanItemSerializer(serializers.ModelSerializer):
    """
    [SOLID - Single Responsibility]
    Gerencia a criação e atualização de Itens de Orçamento específicos de Podologia,
    garantindo que o contexto dos dedos/membros seja salvo na tabela correta.
    """
    podology_context = PodologyProcedureContextSerializer(required=False, allow_null=True)

    class Meta:
        model = TreatmentPlanItem
        fields = [
            'id', 'plan', 'kind', 'status', 'custom_name', 
            'product', 'service', 'quantity', 'value', 'podology_context'
        ]

    def create(self, validated_data):
        # 1. Extrai os dados anatômicos dos pés/mãos enviados pelo React
        context_data = validated_data.pop('podology_context', None)
        
        # 2. Salva o item de orçamento geral (TreatmentPlanItem)
        treatment_plan_item = TreatmentPlanItem.objects.create(**validated_data)
        
        # 3. Se houver dados anatômicos, salva na tabela de podologia amarrando o inquilino (tenant)
        if context_data:
            PodologyProcedureContext.objects.create(
                treatment_plan_item=treatment_plan_item,
                tenant=treatment_plan_item.plan.tenant, # Herda o tenant do plano pai automaticamente
                **context_data
            )
            
        return treatment_plan_item

    def update(self, instance, validated_data):
        context_data = validated_data.pop('podology_context', None)
        
        # Atualiza os dados básicos do item (quantidade, valor, etc.)
        instance = super().update(instance, validated_data)
        
        # Atualiza ou cria o contexto anatômico dos pés/mãos
        if context_data:
            PodologyProcedureContext.objects.update_or_create(
                treatment_plan_item=instance,
                defaults={
                    'tenant': instance.plan.tenant,
                    **context_data
                }
            )
        elif hasattr(instance, 'podology_context'):
            # Se o Frontend limpou a seleção anatômica, remove o registro do dedo
            instance.podology_context.delete()
            
        return instance
