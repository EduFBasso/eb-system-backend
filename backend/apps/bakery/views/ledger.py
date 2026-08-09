from rest_framework import filters, viewsets

from apps.bakery.models import CreditLedgerEntry
from apps.bakery.serializers import CreditLedgerEntrySerializer
from utils.pagination import StandardResultsSetPagination
from utils.permissions import HasActiveBakeryTenant, IsRelatedCustomer

from .base import BakeryTenantScopedMixin


class CreditLedgerEntryViewSet(BakeryTenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CreditLedgerEntrySerializer
    permission_classes = (HasActiveBakeryTenant, IsRelatedCustomer)
    pagination_class = StandardResultsSetPagination
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ("created_at", "amount", "entry_type")
    ordering = ("-created_at", "-id")
    queryset = CreditLedgerEntry.objects.select_related(
        "tenant",
        "customer",
        "customer__user",
        "order",
    )

    def get_queryset(self):
        queryset = super().get_queryset().filter(tenant=self.get_active_tenant())
        membership = getattr(self, "bakery_membership", None)
        is_owner = membership and membership.role == "owner"
        if not is_owner:
            queryset = queryset.filter(customer__user=self.request.user)

        entry_type = self.request.query_params.get("type")
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        customer_id = self.request.query_params.get("customer")
        if customer_id and is_owner:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset