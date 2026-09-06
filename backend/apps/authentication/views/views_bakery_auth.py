from rest_framework_simplejwt.views import TokenObtainPairView

from apps.authentication.serializers.bakery_auth import BakeryTokenObtainPairSerializer


class BakeryTokenObtainPairView(TokenObtainPairView):
    """Endpoint JWT do Bakery."""

    serializer_class = BakeryTokenObtainPairSerializer
