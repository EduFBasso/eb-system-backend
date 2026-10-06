from rest_framework_simplejwt.views import TokenObtainPairView

from apps.authentication.serializers.bakery.auth import (
    BakeryAdminLoginSerializer,
    BakeryCustomerLoginSerializer,
)


class BakeryAdminLoginView(TokenObtainPairView):
    """Login JWT administrativo do Bakery (owner/admin)."""

    serializer_class = BakeryAdminLoginSerializer


class BakeryCustomerLoginView(TokenObtainPairView):
    """Login JWT de cliente do Bakery (member aprovado)."""

    serializer_class = BakeryCustomerLoginSerializer
