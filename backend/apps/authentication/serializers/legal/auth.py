from apps.authentication.serializers.clinic.auth import (
    CustomTokenObtainPairSerializer,
)
from apps.authentication.models import Tenant


class LegalTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    """Serializer Legal para o contrato compartilhado de ``/token/``."""

    def validate(self, attrs):
        attrs = {**attrs, "ecosystem": Tenant.Ecosystem.LEGAL}
        return super().validate(attrs)
