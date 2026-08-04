"""Auth views e serializers relacionados a obtenção de token.

Mantido separado de JWTDeviceAuthentication (que agora está em auth_device.py)
para evitar import parcial durante a avaliação de DEFAULT_AUTHENTICATION_CLASSES.
"""
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

__all__ = [
    'EmailTokenObtainPairView',
]

