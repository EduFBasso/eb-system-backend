from typing import Any, cast

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.authentication.services.permissions import HasTenantCapability
from apps.clinic.models.odonto import TreatmentPlan, TreatmentPlanItem
from apps.clinic.serializers.odonto import (
    TreatmentPlanDetailSerializer,
    TreatmentPlanItemSerializer,
    TreatmentPlanListSerializer,
    TreatmentPlanWriteSerializer,
)


def _refresh_plan_status(plan: TreatmentPlan) -> None:
    """Recalcula o status do plano com base nos itens ativos.

    Se todos os itens ativos (is_active=True) estiverem concluídos ou cancelados,
    o plano passa para COMPLETED. Se houver ao menos um PENDING, volta para PENDING.
    Sem itens ativos, o status não é alterado.
    """
    active_items = plan.items.filter(is_active=True)  # type: ignore[attr-defined]
    total = active_items.count()
    if total == 0:
        return
    pending_count = active_items.filter(status=TreatmentPlanItem.Status.PENDING).count()
    if pending_count == 0:
        plan.status = TreatmentPlan.Status.COMPLETED
        if not plan.completed_at:
            plan.completed_at = timezone.now().date()
    else:
        plan.status = TreatmentPlan.Status.PENDING
        plan.completed_at = None
    plan.save(update_fields=['status', 'completed_at'])


class ProfessionalScopedMixin:
    permission_classes = [permissions.IsAuthenticated, HasTenantCapability('odonto')]

    def current_user(self) -> Any:
        request = cast(Any, getattr(self, 'request', None))
        return getattr(request, 'user', None)

    def current_user_id(self) -> int | None:
        return getattr(self.current_user(), 'id', None)


class TreatmentPlanViewSet(ProfessionalScopedMixin, viewsets.ModelViewSet):
    queryset = TreatmentPlan.objects.select_related('client', 'professional')

    def get_queryset(self):
        user_id = self.current_user_id()
        if not user_id:
            return super().get_queryset().none()
        qs = super().get_queryset().filter(professional_id=user_id)

        client_id = self.request.query_params.get('client')
        status_param = self.request.query_params.get('status')
        if client_id:
            qs = qs.filter(client_id=client_id)
        if status_param:
            qs = qs.filter(status=status_param)
        else:
            # Exclude soft-deleted plans from the default listing.
            qs = qs.exclude(status__in=['archived', 'cancelled'])

        if self.action == 'retrieve':
            qs = qs.prefetch_related('items__dental_context', 'items__service', 'items__product')

        return qs

    def get_serializer_class(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        if self.action == 'list':
            return TreatmentPlanListSerializer
        if self.action == 'retrieve':
            return TreatmentPlanDetailSerializer
        return TreatmentPlanWriteSerializer

    def perform_create(self, serializer: BaseSerializer) -> None:
        user = self.current_user()
        membership = (
            user.tenant_memberships.filter(is_active=True, tenant__is_active=True)
            .order_by('created_at', 'id')
            .select_related('tenant')
            .first()
        )
        tenant = membership.tenant if membership else None
        serializer.save(professional=user, tenant=tenant)

    def perform_update(self, serializer: BaseSerializer) -> None:
        instance = cast(TreatmentPlan, serializer.instance)
        if instance.is_printed:
            raise PermissionDenied(
                'Não é permitido alterar ou excluir dados de um plano já impresso. Crie um novo plano.'
            )
        serializer.save()

    def perform_destroy(self, instance) -> None:  # type: ignore[override]
        if instance.is_printed:
            raise PermissionDenied(
                'Não é permitido alterar ou excluir dados de um plano já impresso. Crie um novo plano.'
            )
        # Hard-delete only when the plan has no items; otherwise archive it.
        if instance.items.exists():  # type: ignore[attr-defined]
            instance.status = 'archived'
            instance.save(update_fields=['status'])
        else:
            instance.delete()

    @action(detail=True, methods=['post'], url_path='mark-printed')
    def mark_printed(self, request, pk=None):
        """Registra a impressão e aplica a preferência de bloqueio da profissional."""
        plan = self.get_object()
        should_lock = bool(getattr(request.user, 'lock_odonto_plan_after_print', True))
        if should_lock and not plan.is_printed:
            plan.is_printed = True
            plan.printed_at = timezone.now()
            plan.save(update_fields=['is_printed', 'printed_at'])
        serializer = self.get_serializer(plan)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TreatmentPlanItemViewSet(ProfessionalScopedMixin, viewsets.ModelViewSet):
    serializer_class = TreatmentPlanItemSerializer
    queryset = TreatmentPlanItem.objects.select_related(
        'plan', 'service', 'product', 'dental_context'
    )

    def get_queryset(self):
        user_id = self.current_user_id()
        if not user_id:
            return super().get_queryset().none()
        qs = super().get_queryset().filter(plan__professional_id=user_id)

        plan_id = self.request.query_params.get('plan')
        status_param = self.request.query_params.get('status')
        if plan_id:
            qs = qs.filter(plan_id=plan_id)
        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        payload = cast(dict[str, Any], serializer.validated_data)
        plan = payload.get('plan')
        if plan is None:
            raise PermissionDenied('Plano de tratamento inválido.')
        if plan.professional_id != self.current_user_id():
            raise PermissionDenied('Plano não pertence ao profissional autenticado.')
        if plan.is_printed:
            raise PermissionDenied(
                'Não é permitido alterar ou excluir dados de um plano já impresso. Crie um novo plano.'
            )
        instance = serializer.save()
        _refresh_plan_status(instance.plan)

    # Fields that a locked (printed) plan still allows updating — payment marking
    # happens after printing the budget, so it must not be blocked by the lock.
    PAYMENT_ONLY_FIELDS = {'status', 'completed_at'}

    def perform_update(self, serializer: BaseSerializer) -> None:
        instance = cast(TreatmentPlanItem, serializer.instance)
        payload = cast(dict[str, Any], serializer.validated_data)
        is_payment_only = set(payload.keys()) <= self.PAYMENT_ONLY_FIELDS
        if instance.plan.is_printed and not is_payment_only:
            raise PermissionDenied(
                'Não é permitido alterar ou excluir dados de um plano já impresso. Crie um novo plano.'
            )
        instance = serializer.save()
        _refresh_plan_status(instance.plan)

    def perform_destroy(self, instance) -> None:  # type: ignore[override]
        if instance.plan.is_printed:
            raise PermissionDenied(
                'Não é permitido alterar ou excluir dados de um plano já impresso. Crie um novo plano.'
            )
        plan = instance.plan
        instance.delete()
        _refresh_plan_status(plan)

    @action(detail=False, methods=['get'], url_path='distinct-names')
    def distinct_names(self, request):
        """Retorna nomes únicos de procedimentos do usuário + catálogo de Service."""
        from apps.clinic.models.inventory import Service

        item_names = set(
            self.get_queryset()
            .filter(custom_name__gt='')
            .values_list('custom_name', flat=True)
            .distinct()
        )
        service_names = set(
            Service.objects.filter(
                tenant__memberships__professional_id=self.current_user_id(),
                tenant__memberships__is_active=True,
                is_active=True,
            ).values_list('name', flat=True)
        )
        names = sorted(item_names.union(service_names), key=str.lower)
        return Response({'names': names}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bulk-status')
    def bulk_status(self, request):
        """Atualiza o status de múltiplos itens de uma vez."""
        item_ids = request.data.get('item_ids', [])
        new_status = request.data.get('status', '')
        completed_at = request.data.get('completed_at')

        if not item_ids or new_status not in TreatmentPlanItem.Status.values:
            return Response({'error': 'Parâmetros inválidos.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_queryset().filter(id__in=item_ids)
        plan_ids = list(qs.values_list('plan_id', flat=True).distinct())

        update_data: dict[str, Any] = {'status': new_status}
        if new_status == TreatmentPlanItem.Status.COMPLETED:
            update_data['completed_at'] = completed_at
        else:
            update_data['completed_at'] = None

        updated_count = qs.update(**update_data)

        for plan in TreatmentPlan.objects.filter(id__in=plan_ids, professional_id=self.current_user_id()):
            _refresh_plan_status(plan)

        return Response({'updated': updated_count, 'status': new_status}, status=status.HTTP_200_OK)


