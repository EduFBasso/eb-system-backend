from rest_framework import filters, viewsets

from apps.bakery.models import Order, OrderItem, Product
from apps.bakery.serializers import OrderItemSerializer, OrderSerializer, ProductSerializer
from utils.pagination import StandardResultsSetPagination
from utils.permissions import (
    HasActiveBakeryTenant,
    IsRelatedCustomer,
    IsTenantStaffOrReadOnly,
)

from .base import BakeryTenantScopedMixin


class ProductViewSet(BakeryTenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = (HasActiveBakeryTenant, IsTenantStaffOrReadOnly)
    pagination_class = StandardResultsSetPagination
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name", "description")
    ordering_fields = ("name", "price", "created_at")
    ordering = ("name",)
    queryset = Product.objects.select_related("tenant")

    def get_queryset(self):
        queryset = super().get_queryset().filter(tenant=self.get_active_tenant())
        membership = getattr(self, "bakery_membership", None)
        if not (membership and membership.role == "owner"):
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_active_tenant())


class OrderViewSet(BakeryTenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = (HasActiveBakeryTenant, IsRelatedCustomer)
    pagination_class = StandardResultsSetPagination
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("customer__nickname", "notes")
    ordering_fields = ("created_at", "delivery_date", "total_value", "status")
    ordering = ("-created_at",)
    queryset = Order.objects.select_related("tenant", "customer", "customer__user").prefetch_related(
        "items__product"
    )

    def get_queryset(self):
        queryset = super().get_queryset().filter(tenant=self.get_active_tenant())
        membership = getattr(self, "bakery_membership", None)
        if not (membership and membership.role == "owner"):
            queryset = queryset.filter(customer__user=self.request.user)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status__in=status_value.split(","))
        customer_nickname = self.request.query_params.get("customer_nickname")
        if customer_nickname:
            queryset = queryset.filter(customer__nickname__icontains=customer_nickname)
        return queryset

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_active_tenant())


class OrderItemViewSet(BakeryTenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = (HasActiveBakeryTenant, IsRelatedCustomer)
    pagination_class = StandardResultsSetPagination
    queryset = OrderItem.objects.select_related(
        "tenant",
        "order",
        "order__customer",
        "order__customer__user",
        "product",
    )

    def get_queryset(self):
        queryset = super().get_queryset().filter(tenant=self.get_active_tenant())
        membership = getattr(self, "bakery_membership", None)
        if not (membership and membership.role == "owner"):
            queryset = queryset.filter(order__customer__user=self.request.user)

        order_id = self.request.query_params.get("order")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset