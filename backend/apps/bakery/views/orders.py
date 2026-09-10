from django.db import transaction
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.authentication.models import TenantMembership
from apps.bakery.models import CreditLedgerEntry, Order, OrderItem, Product
from apps.bakery.serializers import OrderItemSerializer, OrderSerializer, ProductSerializer
from apps.bakery.serializers.orders import CancelOrderSerializer, UpdateOrderStatusSerializer
from apps.bakery.services.notifications import notify_owner_order_cancelled
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
        if not (
            membership
            and membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)
        ):
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
        if not (
            membership
            and membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)
        ):
            queryset = queryset.filter(customer__user=self.request.user)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status__in=status_value.split(","))
        customer_nickname = self.request.query_params.get("customer_nickname")
        if customer_nickname:
            queryset = queryset.filter(customer__nickname__icontains=customer_nickname)
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if self.request.query_params.get("open_only", "").lower() == "true":
            queryset = queryset.filter(paid_at__isnull=True, cancelled_at__isnull=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_active_tenant())

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Pedidos não podem ser editados. Use as ações de status ou cancelamento."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Pedidos não podem ser excluídos. Cancele o pedido para preservar o histórico."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _is_management(self) -> bool:
        membership = getattr(self, "bakery_membership", None)
        return bool(
            getattr(self.request.user, "is_staff", False)
            or (
                membership
                and membership.role
                in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)
            )
        )

    def _validate_admin_password(self, password: str | None) -> Response | None:
        if not password:
            return Response(
                {"detail": "admin_password é obrigatória."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self.request.user.check_password(password):
            return Response(
                {"detail": "Senha do administrador incorreta."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return None

    def _validate_customer_password(self, password: str | None) -> Response | None:
        if not password:
            return Response(
                {"detail": "customer_password é obrigatória."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self.request.user.check_password(password):
            return Response(
                {"detail": "Senha do cliente incorreta."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return None

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        command = CancelOrderSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        order = self.get_object()
        is_customer_owner = order.customer.user_id == request.user.id and not getattr(
            request.user, "is_staff", False
        )
        if is_customer_owner:
            denied = self._validate_customer_password(
                command.validated_data.get("customer_password")
            )
            if denied:
                return denied
        elif self._is_management():
            denied = self._validate_admin_password(command.validated_data.get("admin_password"))
            if denied:
                return denied

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk, tenant=order.tenant)
            if order.status == Order.Status.CANCELLED:
                return Response(OrderSerializer(order).data)
            if order.status != Order.Status.PENDING:
                return Response(
                    {"detail": "Apenas pedidos pendentes podem ser cancelados."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order.status = Order.Status.CANCELLED
            order.cancellation_reason = command.validated_data["reason"]
            order.cancelled_at = timezone.now()
            order.save(
                update_fields=("status", "cancellation_reason", "cancelled_at", "updated_at")
            )
            if order.payment_method == Order.PaymentMethod.CREDIT:
                CreditLedgerEntry.objects.get_or_create(
                    tenant=order.tenant,
                    reference_key=f"order:{order.pk}:cancel-credit",
                    defaults={
                        "customer": order.customer,
                        "order": order,
                        "entry_type": CreditLedgerEntry.EntryType.CREDIT,
                        "amount": order.total_value,
                        "description": f"Credit reversal for cancelled order #{order.pk}",
                    },
                )
            actor = " ".join(
                part for part in (request.user.first_name, request.user.last_name) if part
            ) or request.user.email
            transaction.on_commit(
                lambda: notify_owner_order_cancelled(order, actor=actor)
            )

        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        if not self._is_management():
            return Response(
                {"detail": "Apenas o owner ou administrador pode alterar o status."},
                status=status.HTTP_403_FORBIDDEN,
            )
        command = UpdateOrderStatusSerializer(data=request.data)
        command.is_valid(raise_exception=True)
        denied = self._validate_admin_password(command.validated_data["admin_password"])
        if denied:
            return denied

        order = self.get_object()
        target = command.validated_data["status"]
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk, tenant=order.tenant)
            if target == Order.Status.CONFIRMED and order.status == Order.Status.CONFIRMED:
                if order.paid_at is None:
                    order.paid_at = timezone.now()
                    order.save(update_fields=("paid_at", "updated_at"))
                if order.payment_method == Order.PaymentMethod.CREDIT:
                    CreditLedgerEntry.objects.get_or_create(
                        tenant=order.tenant,
                        reference_key=f"order:{order.pk}:payment-credit",
                        defaults={
                            "customer": order.customer,
                            "order": order,
                            "entry_type": CreditLedgerEntry.EntryType.CREDIT,
                            "amount": order.total_value,
                            "description": f"Payment received for order #{order.pk}",
                        },
                    )
                return Response(OrderSerializer(order).data)
            allowed_transition = {
                Order.Status.PENDING: Order.Status.CONFIRMED,
                Order.Status.CONFIRMED: Order.Status.DELIVERED,
            }.get(order.status)
            if target == order.status:
                return Response(OrderSerializer(order).data)
            if target != allowed_transition:
                return Response(
                    {"detail": f"Transição de {order.status} para {target} não permitida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.status = target
            update_fields = ["status", "updated_at"]
            if target == Order.Status.CONFIRMED:
                order.paid_at = timezone.now()
                update_fields.append("paid_at")
                if order.payment_method == Order.PaymentMethod.CREDIT:
                    CreditLedgerEntry.objects.get_or_create(
                        tenant=order.tenant,
                        reference_key=f"order:{order.pk}:payment-credit",
                        defaults={
                            "customer": order.customer,
                            "order": order,
                            "entry_type": CreditLedgerEntry.EntryType.CREDIT,
                            "amount": order.total_value,
                            "description": f"Payment received for order #{order.pk}",
                        },
                    )
            order.save(update_fields=update_fields)
        return Response(OrderSerializer(order).data)


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
        if not (
            membership
            and membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)
        ):
            queryset = queryset.filter(order__customer__user=self.request.user)

        order_id = self.request.query_params.get("order")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset