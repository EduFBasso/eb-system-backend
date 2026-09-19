from apps.clinic.serializers.clients import ClientSerializer, ClientBasicSerializer
from .serializers_professionals import (
    ProfessionalSerializer,
    ProfessionalBasicSerializer
)
from .clinic.auth import CustomTokenObtainPairSerializer
from .clinic.settings import ProfessionalSettingsSerializer

__all__ = [
    "ClientSerializer",
    "ClientBasicSerializer",
    "ProfessionalSerializer",
    "ProfessionalBasicSerializer",
    "CustomTokenObtainPairSerializer",
    "ProfessionalSettingsSerializer",
]
