# backend/apps/authentication/serializers/serializers_auth.py
from apps.authentication.serializers.clinic.auth import CustomTokenObtainPairSerializer
from apps.authentication.serializers.legal.auth import LegalTokenObtainPairSerializer

__all__ = [
    "CustomTokenObtainPairSerializer",
    "LegalTokenObtainPairSerializer",
]
