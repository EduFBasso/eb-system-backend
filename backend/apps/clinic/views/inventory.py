from rest_framework import viewsets, permissions
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Supplier, Product, StockMove, Service, ServiceMaterial
from .serializers import (
    SupplierSerializer,
    ProductSerializer,
    StockMoveSerializer,
    ServiceSerializer,
    ServiceMaterialSerializer,
)


class BaseScopedViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication, SessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        return qs.filter(professional=user)

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user)


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

    def get_queryset(self):
        qs = super(BaseScopedViewSet, self).get_queryset()
        user = self.request.user
        # Filtra por materiais cujo serviço pertence ao profissional logado
        return qs.filter(service__professional=user)

    def perform_create(self, serializer):
        # Garante que o material está associado a um serviço do profissional logado
        service = serializer.validated_data.get('service')
        if service and service.professional_id != self.request.user.id: # type: ignore
            raise PermissionDenied('Serviço não pertence ao profissional atual.')
        serializer.save()
