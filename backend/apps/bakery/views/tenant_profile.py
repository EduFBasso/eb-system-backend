from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bakery.serializers.tenant_profile import BakeryTenantProfileSerializer
from utils.permissions import HasActiveBakeryTenant, IsBakeryOwner, _get_bakery_membership


class BakeryTenantProfileView(APIView):
    """Lê e atualiza os dados da empresa Bakery do token atual."""

    permission_classes = (IsAuthenticated, HasActiveBakeryTenant)

    def get_permissions(self):
        permissions = list(super().get_permissions())
        if self.request.method in ("PATCH", "PUT"):
            permissions.append(IsBakeryOwner())
        return permissions

    def get_tenant(self):
        membership = _get_bakery_membership(self.request)
        return membership.tenant if membership is not None else None

    def get(self, request):
        tenant = self.get_tenant()
        if tenant is None:
            return Response(
                {"detail": "Usuário não possui acesso a um tenant Bakery ativo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(BakeryTenantProfileSerializer(tenant).data)

    def patch(self, request):
        return self._update(request)

    def put(self, request):
        return self._update(request)

    def _update(self, request):
        tenant = self.get_tenant()
        if tenant is None:
            return Response(
                {"detail": "Usuário não possui acesso a um tenant Bakery ativo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BakeryTenantProfileSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)