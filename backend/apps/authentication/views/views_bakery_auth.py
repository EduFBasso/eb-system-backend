from rest_framework_simplejwt.views import TokenObtainPairView

from apps.authentication.serializers.bakery_auth import BakeryTokenObtainPairSerializer


class BakeryTokenObtainPairView(TokenObtainPairView):
    """Endpoint JWT do Bakery sem TOTP/2FA.

    Mantido isolado do fluxo clinico para evitar acoplamento de regras de MFA.
    """

    serializer_class = BakeryTokenObtainPairSerializer
