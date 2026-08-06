from django.db import transaction
from rest_framework import filters, viewsets

from apps.bakery.models import BakeryCustomer, BakeryCustomerAuditLog
from apps.bakery.serializers import BakeryCustomerSerializer
from utils.pagination import StandardResultsSetPagination
from utils.permissions import HasActiveBakeryTenant, IsCustomerOrAdmin

from .base import BakeryTenantScopedMixin


class BakeryCustomerViewSet(BakeryTenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = BakeryCustomerSerializer
    permission_classes = (HasActiveBakeryTenant, IsCustomerOrAdmin)
    pagination_class = StandardResultsSetPagination
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("nickname", "company_name", "cpf", "cnpj", "phone")
    ordering_fields = ("nickname", "status", "created_at", "credit_limit")
    ordering = ("nickname",)
    queryset = BakeryCustomer.objects.select_related("tenant", "user")

    def get_queryset(self):
        tenant = self.get_active_tenant()
        queryset = super().get_queryset().filter(tenant=tenant)
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def perform_create(self, serializer):
        tenant = self.get_active_tenant()
        user = serializer.validated_data.get("user")
        if not self.request.user.is_staff or user is None:
            user = self.request.user
        serializer.save(tenant=tenant, user=user)

    @transaction.atomic
    def perform_update(self, serializer):
        previous = self.get_object()
        previous_status = previous.status
        previous_credit_limit = previous.credit_limit
        customer = serializer.save(tenant=self.get_active_tenant(), user=previous.user)

        action = None
        details = {}
        if customer.status != previous_status:
            if customer.status == BakeryCustomer.ApprovalStatus.APPROVED:
                action = BakeryCustomerAuditLog.Action.APPROVED
            elif customer.status == BakeryCustomer.ApprovalStatus.BLOCKED:
                action = BakeryCustomerAuditLog.Action.BLOCKED
            elif previous_status == BakeryCustomer.ApprovalStatus.BLOCKED:
                action = BakeryCustomerAuditLog.Action.UNBLOCKED
            details["previous_status"] = previous_status
            details["new_status"] = customer.status
        elif customer.credit_limit != previous_credit_limit:
            action = BakeryCustomerAuditLog.Action.CREDIT_LIMIT_UPDATED
            details["previous_credit_limit"] = str(previous_credit_limit)
            details["new_credit_limit"] = str(customer.credit_limit)

        if action:
            BakeryCustomerAuditLog.objects.create(
                tenant=self.get_active_tenant(),
                customer=customer,
                action=action,
                admin_user=self.request.user,
                details=details,
            )