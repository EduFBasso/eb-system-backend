"""Auth views e serializers relacionados a obtenção de token."""
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.authentication.serializers.clinic.auth import CustomTokenObtainPairSerializer

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

__all__ = [
    'EmailTokenObtainPairView',
]

