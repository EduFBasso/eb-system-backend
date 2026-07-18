from typing import cast

from django.db.models import QuerySet
from rest_framework import viewsets, permissions, generics
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django.utils import timezone

from .models import Appointment, Charge, ClinicalRecord, Encounter, FinalizeAudit
from .serializers import (
    AppointmentSerializer,
    ChargeSerializer,
    ClinicalRecordSerializer,
    EncounterSerializer,
    FinalizeAuditSerializer,
)
from .state_utils import promote_overdue_scheduled_to_pending, promote_scheduled_to_ongoing


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
        if user and getattr(user, "id", None):
            return qs.filter(professional_id=user.id)
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user)


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
        # restringe a agenda ao profissional logado
        if user and getattr(user, "id", None):
            qs = qs.filter(professional_id=user.id)
        else:
            qs = qs.none()
        # Promoção temporal oportunista: limitar a leituras de agenda.
        # Evita escritas implícitas desnecessárias em fluxos de update/destroy.
        if getattr(self, "action", None) in {"list", "next_for_client"}:
            promote_scheduled_to_ongoing(qs)
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
        obj = serializer.save(professional=user)
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

    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        """Encerra a fase programável do compromisso, movendo-o para 'pending'.

        Regras:
        - Apenas o profissional dono pode finalizar.
        - Permitido se o status atual for 'scheduled' ou 'ongoing'.
        - Não permite antes do início (too_early 422).
        - Ajusta o fim (end_at) SOMENTE se ainda em andamento (now < end_at) para refletir duração real.
          Se o compromisso já terminou (now >= end_at) mantemos o fim planejado.
        """
        obj = self.get_object()
        # Permissão explícita
        if getattr(request.user, "id", None) != getattr(obj.professional, "id", None):
            return Response({"detail": "forbidden"}, status=403)
        if obj.status == obj.Status.PENDING:
            return Response(self.get_serializer(obj).data, status=200)
        if obj.status == obj.Status.DONE:
            # idempotente
            return Response(self.get_serializer(obj).data, status=200)
        if obj.status == obj.Status.CANCELED:
            return Response({"detail": "compromisso cancelado não pode ser concluído"}, status=400)

        now = timezone.now()
        # Capturar headers do dispositivo e horário do cliente
        dev_id = request.headers.get("x-device-id") or request.headers.get("X-Device-Id") or None
        dev_info = request.headers.get("x-device-info") or request.headers.get("X-Device-Info") or ""
        client_now_iso = request.headers.get("x-client-now") or request.headers.get("X-Client-Now") or None
        client_now_dt = None
        if client_now_iso:
            try:
                from django.utils.dateparse import parse_datetime

                client_now_dt = parse_datetime(client_now_iso)
            except Exception:
                client_now_dt = None
        if obj.start_at and now < obj.start_at:
            # 422 sinaliza regra de negócio
            return Response({"detail": "compromisso ainda não iniciou", "code": "too_early"}, status=422)

        # Move para pending; encurta end_at apenas se em andamento
        obj.status = obj.Status.PENDING
        adjusted = False
        if obj.end_at and now < obj.end_at:
            obj.end_at = now
            adjusted = True
            if obj.start_at and obj.end_at <= obj.start_at:
                obj.end_at = obj.start_at
        # Definir finalized_at uma única vez (idempotente)
        if not getattr(obj, "finalized_at", None):
            obj.finalized_at = now
        # Gravar device que finalizou (opcional)
        try:
            if dev_id:
                obj.ended_device_id = (dev_id or "")[:64]
            if dev_info:
                try:
                    from urllib.parse import unquote

                    dev_info = unquote(dev_info)
                except Exception:
                    pass
                obj.ended_device_info = (dev_info or "")[:4000]
            obj.save(update_fields=[
                "status",
                "end_at",
                "finalized_at",
                "ended_device_id",
                "ended_device_info",
                "updated_at",
            ])
        except Exception:
            obj.save(update_fields=["status", "end_at", "finalized_at", "updated_at"])

        # Registrar auditoria
        try:
            drift_ms = None
            if client_now_dt is not None:
                # usar timezone-aware e converter se necessário
                if timezone.is_naive(client_now_dt):
                    client_now_dt = timezone.make_aware(client_now_dt, timezone=timezone.utc)
                drift_ms = int((now - client_now_dt).total_seconds() * 1000)
            FinalizeAudit.objects.create(
                appointment=obj,
                professional=obj.professional,
                client=obj.client,
                device_id=dev_id[:64] if dev_id else None,
                device_info=(dev_info or "")[:4000],
                client_now=client_now_dt,
                server_now=now,
                drift_ms=drift_ms,
                adjusted_times=adjusted,
                reason="in_window" if adjusted else "finished",
            )
        except Exception:
            pass

        return Response(self.get_serializer(obj).data, status=200)

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
                    "detail": "compromisso deve ser finalizado antes de ser concluído",
                    "code": "must_finalize_first",
                },
                status=409,
            )

        obj.status = obj.Status.DONE
        obj.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(obj).data, status=200)


class IsStaffOnly(permissions.BasePermission):
    def has_permission(self, request, view):  # pyright: ignore[reportIncompatibleMethodOverride]
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class FinalizeAuditListView(TypedRequestMixin, generics.ListAPIView):
    """Admin-only list endpoint to inspect finalize audits with optional filters.

    Query params:
    - appointment: int
    - device_id: str (exact)
    - start: ISO datetime (created_at >=)
    - end: ISO datetime (created_at <=)
    """

    serializer_class = FinalizeAuditSerializer
    permission_classes = [IsStaffOnly]
    queryset = FinalizeAudit.objects.select_related("appointment", "professional", "client")

    def get_queryset(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        qs = self.base_queryset()
        appt_id = self.query_param("appointment")
        device_id = self.query_param("device_id")
        start = self.query_param("start")
        end = self.query_param("end")
        if appt_id:
            try:
                qs = qs.filter(appointment_id=int(appt_id))
            except Exception:
                pass
        if device_id:
            qs = qs.filter(device_id=device_id)
        if start:
            try:
                qs = qs.filter(created_at__gte=start)
            except Exception:
                pass
        if end:
            try:
                qs = qs.filter(created_at__lte=end)
            except Exception:
                pass
        return qs.order_by("-created_at")


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
