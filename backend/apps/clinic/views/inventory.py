from rest_framework import viewsets, permissions
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.authentication.models import Tenant
from apps.clinic.models.inventory import Supplier, Product, StockMove, Service, ServiceMaterial
from apps.clinic.serializers.inventory import (
    SupplierSerializer,
    ProductSerializer,
    StockMoveSerializer,
    ServiceSerializer,
    ServiceMaterialSerializer,
)


class BaseScopedViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication, SessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)
    tenant_lookup = "tenant"

    def active_tenant(self):
        return (
            Tenant.objects.filter(
                memberships__professional=self.request.user,
                memberships__is_active=True,
                is_active=True,
            )
            .order_by("memberships__created_at", "id")
            .first()
        )

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = self.active_tenant()
        if tenant is None:
            return qs.none()
        return qs.filter(**{self.tenant_lookup: tenant})

    def perform_create(self, serializer):
        tenant = self.active_tenant()
        if tenant is None:
            raise PermissionDenied("Profissional sem clínica ativa.")
        serializer.save(tenant=tenant)


class SupplierViewSet(BaseScopedViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


class ProductViewSet(BaseScopedViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class StockMoveViewSet(BaseScopedViewSet):
    queryset = StockMove.objects.all()
    serializer_class = StockMoveSerializer


class ServiceViewSet(BaseScopedViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class ServiceMaterialViewSet(BaseScopedViewSet):
    queryset = ServiceMaterial.objects.all()
    serializer_class = ServiceMaterialSerializer
    tenant_lookup = "service__tenant"

    def get_queryset(self):
        return super().get_queryset()

    def perform_create(self, serializer):
        tenant = self.active_tenant()
        service = serializer.validated_data.get('service')
        product = serializer.validated_data.get('product')
        if tenant is None or not service or service.tenant_id != tenant.id:
            raise PermissionDenied('Serviço não pertence à clínica atual.')
        if not product or product.tenant_id != tenant.id:
            raise PermissionDenied('Produto não pertence à clínica atual.')
        serializer.save()
