from rest_framework import serializers
from apps.clinic.models.podologia import PodologyProcedureContext

class PodologyProcedureContextSerializer(serializers.ModelSerializer):
    """
    Serializa os dados anatômicos dos Pés e Mãos para o Frontend (React).
    """
    class Meta:
        model = PodologyProcedureContext
        fields = ['id', 'scope', 'location_number']

