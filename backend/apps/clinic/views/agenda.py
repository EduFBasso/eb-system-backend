from typing import cast

from django.db.models import QuerySet
from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django.utils import timezone

from apps.clinic.models.agenda import Appointment, Charge, ClinicalRecord, Encounter
from apps.clinic.serializers.agenda import (
    AppointmentSerializer,
    ChargeSerializer,
    ClinicalRecordSerializer,
    EncounterSerializer,
)
from .state_utils import promote_overdue_scheduled_to_pending


def _get_active_tenant(user):
    """Resolve the active tenant from the authenticated user's memberships."""
    if not user or not getattr(user, "is_authenticated", False):
        return None

    membership = (
        user.tenant_memberships.select_related("tenant")
        .filter(is_active=True, tenant__is_active=True)
        .order_by("created_at", "id")
        .first()
    )
    if membership:
        return membership.tenant
    return None


class TypedRequestMixin:
    def drf_request(self) -> Request:
        return cast(Request, getattr(self, "request"))

    def query_param(self, key: str) -> str | None:
        return self.drf_request().query_params.get(key)

    def query_param_int(self, key: str) -> int | None:
        raw = self.query_param(key)
        if raw in (None, ""):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def base_queryset(self) -> QuerySet:
        queryset = getattr(self, "queryset", None)
        assert queryset is not None, f"{self.__class__.__name__} must define queryset"
        return cast(QuerySet, queryset)


class IsProfessionalOrReadOnly(permissions.BasePermission):
    """Permissão simples: usuário autenticado pode ler; alterações restritas ao próprio profissional.
    Assumimos que request.user é Professional.
    """

    def has_permission(self, request, view):  # pyright: ignore[reportIncompatibleMethodOverride]
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj: Appointment):
        return getattr(request.user, "id", None) == getattr(obj.professional, "id", None)


class ProfessionalOwnedViewSet(TypedRequestMixin, viewsets.ModelViewSet):
    permission_classes = [IsProfessionalOrReadOnly]

    def get_queryset(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        qs = self.base_queryset()
        user = getattr(self.request, "user", None)

        tenant = _get_active_tenant(user)
        if tenant is not None:
            # Compat: include legacy rows with tenant=NULL that still belong to this tenant's professionals.
            return qs.filter(
                Q(tenant_id=tenant.id)
                | Q(
                    tenant__isnull=True,
                    professional__tenant_memberships__tenant=tenant,
                    professional__tenant_memberships__is_active=True,
                    professional__tenant_memberships__tenant__is_active=True,
                )
            ).distinct()

        if user and getattr(user, "id", None):
            return qs.filter(professional_id=user.id)
        return qs.none()

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        tenant = _get_active_tenant(user)
        serializer.save(professional=user, tenant=tenant)


class AppointmentViewSet(TypedRequestMixin, viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [IsProfessionalOrReadOnly]
    queryset = Appointment.objects.select_related("professional", "client")
    ordering_fields = {"start_at", "end_at", "created_at", "updated_at"}

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # garante request no contexto para validação que depende do usuário
        ctx["request"] = getattr(self, "request", None)
        return ctx

    def get_queryset(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        qs = self.base_queryset()
        user = getattr(self.request, "user", None)

        tenant = _get_active_tenant(user)
        # Restringe a agenda ao tenant ativo da profissional.
        if tenant is not None:
            qs = qs.filter(
                Q(tenant_id=tenant.id)
                | Q(
                    tenant__isnull=True,
                    professional__tenant_memberships__tenant=tenant,
                    professional__tenant_memberships__is_active=True,
                    professional__tenant_memberships__tenant__is_active=True,
                )
            ).distinct()
        elif user and getattr(user, "id", None):
            # Compat fallback para fluxos sem tenant ativo.
            qs = qs.filter(professional_id=user.id)
        else:
            qs = qs.none()
        # Promoção temporal oportunista: limitar a leituras de agenda.
        # Evita escritas implícitas desnecessárias em fluxos de update/destroy.
        if getattr(self, "action", None) in {"list", "next_for_client"}:
            promote_overdue_scheduled_to_pending(qs)
        # filtros opcionais ?start=2025-09-01T00:00:00&end=2025-09-02T00:00:00&client=<id>
        start = self.query_param("start")
        end = self.query_param("end")
        client_id = self.query_param("client")
        status_val = self.query_param("status")

        if start:
            try:
                qs = qs.filter(end_at__gt=start)
            except Exception:
                pass
        if end:
            try:
                qs = qs.filter(start_at__lt=end)
            except Exception:
                pass
        if client_id:
            qs = qs.filter(client_id=client_id)
        if status_val:
            qs = qs.filter(status=status_val)

        if getattr(self, "action", None) == "list":
            ordering = self.query_param("ordering")
            if ordering:
                ordering_field = ordering.lstrip("-")
                if ordering_field in self.ordering_fields:
                    qs = qs.order_by(ordering)

            limit = self.query_param_int("limit")
            if limit is not None:
                limit = max(1, min(limit, 500))
                qs = qs[:limit]
        return qs

    def perform_create(self, serializer):
        # profissional sempre é o usuário autenticado
        user = getattr(self.request, "user", None)
        tenant = _get_active_tenant(user)
        obj = serializer.save(professional=user, tenant=tenant)
        # Marcar device de criação (não obrigatório)
        try:
            dev_id = self.request.headers.get("x-device-id") or self.request.headers.get("X-Device-Id") or None
            dev_info = self.request.headers.get("x-device-info") or self.request.headers.get("X-Device-Info") or ""
            if dev_id:
                obj.created_device_id = dev_id[:64]
            if dev_info:
                # X-Device-Info pode vir como URL-encoded
                try:
                    from urllib.parse import unquote

                    dev_info = unquote(dev_info)
                except Exception:
                    pass
                obj.created_device_info = dev_info[:4000]
            obj.save(update_fields=["created_device_id", "created_device_info", "updated_at"])
        except Exception:
            pass

    # Impede exclusão: histórico deve ser preservado. Fornecemos ação de cancelamento.
    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Exclusão não permitida. Cancele o agendamento."}, status=405)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        obj = self.get_object()
        # Apenas profissional dono pode cancelar (permission_classes já cobre update, mas reforçamos)
        if getattr(request.user, "id", None) != getattr(obj.professional, "id", None):
            return Response({"detail": "forbidden"}, status=403)
        if obj.status == Appointment.Status.CANCELED:
            return Response({"detail": "já cancelado"}, status=200)
        if obj.status == Appointment.Status.DONE:
            return Response(
                {"detail": "compromisso concluído não pode ser cancelado"},
                status=400,
            )
        obj.status = Appointment.Status.CANCELED
        from django.utils import timezone as _tz
        if not getattr(obj, "canceled_at", None):
            obj.canceled_at = _tz.now()
            update_fields = ["status", "canceled_at", "updated_at"]
        else:
            update_fields = ["status", "updated_at"]
        obj.save(update_fields=update_fields)
        return Response(self.get_serializer(obj).data, status=200)

    @action(detail=True, methods=["post"], url_path="confirm-whatsapp")
    def confirm_whatsapp(self, request, pk=None):
        """Marca whatsapp_confirmed=True no agendamento.

        Chamado pelo sw.js quando o profissional clica em 'Sim, enviar WhatsApp'
        na notificação push, ou pelo modal interno do app.
        Idempotente — chamadas repetidas retornam 200 sem erro.
        """
        obj = self.get_object()
        if not obj.whatsapp_confirmed:
            obj.whatsapp_confirmed = True
            obj.save(update_fields=["whatsapp_confirmed", "updated_at"])
        return Response({"ok": True, "whatsapp_confirmed": True}, status=200)

    @action(detail=False, methods=["get"], url_path="next")
    def next_for_client(self, request):
        """Retorna o próximo agendamento futuro opcionalmente filtrando por client=<id>."""
        now = timezone.now()
        qs = self.get_queryset().filter(start_at__gte=now).order_by("start_at")
        obj = qs.first()
        if not obj:
            return Response({"detail": "no-upcoming"})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], url_path="done")
    def done(self, request, pk=None):
        """Resolve explicitamente um compromisso pendente como concluído."""
        obj = self.get_object()
        if getattr(request.user, "id", None) != getattr(obj.professional, "id", None):
            return Response({"detail": "forbidden"}, status=403)
        if obj.status == obj.Status.DONE:
            return Response(self.get_serializer(obj).data, status=200)
        if obj.status == obj.Status.CANCELED:
            return Response(
                {"detail": "compromisso cancelado não pode ser concluído"},
                status=400,
            )
        if obj.status != obj.Status.PENDING:
            return Response(
                {
                    "detail": "compromisso deve estar pendente antes de ser concluído",
                    "code": "must_be_pending_first",
                },
                status=409,
            )

        obj.status = obj.Status.DONE
        obj.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(obj).data, status=200)


class EncounterViewSet(ProfessionalOwnedViewSet):
    serializer_class = EncounterSerializer
    queryset = Encounter.objects.select_related("professional", "client", "appointment")

    def get_queryset(self):
        qs = super().get_queryset()
        client_id = self.query_param("client")
        appointment_id = self.query_param("appointment")
        status_val = self.query_param("status")
        if client_id:
            qs = qs.filter(client_id=client_id)
        if appointment_id:
            qs = qs.filter(appointment_id=appointment_id)
        if status_val:
            qs = qs.filter(status=status_val)
        return qs

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Exclusão não permitida. Cancele ou encerre o atendimento."}, status=405)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        encounter = self.get_object()
        if encounter.status == Encounter.Status.CLOSED:
            return Response(self.get_serializer(encounter).data, status=200)
        if encounter.status == Encounter.Status.CANCELED:
            return Response({"detail": "Atendimento cancelado não pode ser encerrado."}, status=400)
        encounter.status = Encounter.Status.CLOSED
        if encounter.ended_at is None:
            encounter.ended_at = timezone.now()
        encounter.save()
        return Response(self.get_serializer(encounter).data, status=200)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        encounter = self.get_object()
        if encounter.status == Encounter.Status.CANCELED:
            return Response(self.get_serializer(encounter).data, status=200)
        encounter.status = Encounter.Status.CANCELED
        if encounter.ended_at is None:
            encounter.ended_at = timezone.now()
        encounter.save()
        return Response(self.get_serializer(encounter).data, status=200)


class ClinicalRecordViewSet(ProfessionalOwnedViewSet):
    serializer_class = ClinicalRecordSerializer
    queryset = ClinicalRecord.objects.select_related("professional", "client", "encounter")

    def get_queryset(self):
        qs = super().get_queryset()
        client_id = self.query_param("client")
        encounter_id = self.query_param("encounter")
        record_type = self.query_param("record_type")
        if client_id:
            qs = qs.filter(client_id=client_id)
        if encounter_id:
            qs = qs.filter(encounter_id=encounter_id)
        if record_type:
            qs = qs.filter(record_type=record_type)
        return qs

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Exclusão não permitida. Preserve o histórico do prontuário."}, status=405)


class ChargeViewSet(ProfessionalOwnedViewSet):
    serializer_class = ChargeSerializer
    queryset = Charge.objects.select_related(
        "professional", "client", "encounter", "appointment"
    ).prefetch_related("items")

    def get_queryset(self):
        qs = super().get_queryset()
        client_id = self.query_param("client")
        encounter_id = self.query_param("encounter")
        appointment_id = self.query_param("appointment")
        status_val = self.query_param("status")
        charge_type = self.query_param("charge_type")
        if client_id:
            qs = qs.filter(client_id=client_id)
        if encounter_id:
            qs = qs.filter(encounter_id=encounter_id)
        if appointment_id:
            qs = qs.filter(appointment_id=appointment_id)
        if status_val:
            qs = qs.filter(status=status_val)
        if charge_type:
            qs = qs.filter(charge_type=charge_type)
        return qs

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Exclusão não permitida. Cancele a cobrança."}, status=405)

    @action(detail=True, methods=["post"], url_path="mark-sent")
    def mark_sent(self, request, pk=None):
        charge = self.get_object()
        if charge.status == Charge.Status.CANCELED:
            return Response({"detail": "Cobrança cancelada não pode ser enviada."}, status=400)
        if charge.status != Charge.Status.PAID:
            charge.status = Charge.Status.SENT
        if charge.shared_at is None:
            charge.shared_at = timezone.now()
        charge.save()
        return Response(self.get_serializer(charge).data, status=200)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        charge = self.get_object()
        if charge.status == Charge.Status.CANCELED:
            return Response({"detail": "Cobrança cancelada não pode ser paga."}, status=400)
        charge.status = Charge.Status.PAID
        if charge.paid_at is None:
            charge.paid_at = timezone.now()
        charge.save()
        return Response(self.get_serializer(charge).data, status=200)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        charge = self.get_object()
        if charge.status == Charge.Status.PAID:
            return Response({"detail": "Cobrança paga não pode ser cancelada."}, status=400)
        charge.status = Charge.Status.CANCELED
        charge.save()
        return Response(self.get_serializer(charge).data, status=200)
