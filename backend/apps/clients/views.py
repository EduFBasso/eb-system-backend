from django.db.models import Q, OuterRef, Subquery, DateTimeField, CharField, Case, When, IntegerField
from django.utils import timezone
from apps.agenda.models import Appointment
from apps.agenda.state_utils import promote_scheduled_to_ongoing, promote_overdue_scheduled_to_pending
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db import IntegrityError
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from apps.clients.models import Client
from apps.clients.serializers import ClientSerializer, ClientBasicSerializer


def _get_active_tenant(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    membership = (
        user.tenant_memberships.select_related('tenant')
        .filter(is_active=True, tenant__is_active=True)
        .order_by('created_at', 'id')
        .first()
    )
    if membership:
        return membership.tenant
    return None


class ClientViewSet(ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['first_name', 'last_name', 'city', 'state']
    ordering = ['first_name']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['tenant'] = _get_active_tenant(self.request.user)
        return context

    def get_queryset(self): # type: ignore
        user_id = getattr(self.request.user, 'id', None)
        if not user_id:
            return Client.objects.none()
        tenant = _get_active_tenant(self.request.user)
        if tenant is None:
            return Client.objects.none()

        from django.db.models import Prefetch
        from apps.anamnesis.models import AnamneseBase, AnamnesePodologia

        queryset = (
            Client.objects.filter(professional_id=user_id, tenant_id=tenant.id)
            .select_related('tenant', 'professional')
            .prefetch_related(
                Prefetch(
                    'anamneses_base',
                    queryset=AnamneseBase.objects.filter(
                        tenant_id=tenant.id,
                        professional_id=user_id,
                    ),
                ),
                Prefetch(
                    'anamneses_podologia',
                    queryset=AnamnesePodologia.objects.filter(
                        tenant_id=tenant.id,
                        professional_id=user_id,
                    ),
                ),
            )
        )
        nome = self.request.query_params.get('nome') # type: ignore
        if nome:
            queryset = queryset.filter(first_name__icontains=nome)
        return queryset

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError as e:
            msg = str(e).lower()
            if 'phone' in msg or 'phone_digits' in msg or 'register_client_phone' in msg:
                raise ValidationError({'phone': ['Este telefone já cadastrado']})
            raise

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError as e:
            msg = str(e).lower()
            if 'phone' in msg or 'phone_digits' in msg or 'register_client_phone' in msg:
                raise ValidationError({'phone': ['Este telefone já cadastrado']})
            raise

    def destroy(self, request, *args, **kwargs):
        client = self.get_object()
        with transaction.atomic():
            client.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



class ClientBasicViewSet(ReadOnlyModelViewSet):
    serializer_class = ClientBasicSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self): # type: ignore
        nome = self.request.query_params.get('nome', '').strip() # type: ignore
        user_id = getattr(self.request.user, 'id', None)
        if not user_id:
            return Client.objects.none()
        tenant = _get_active_tenant(self.request.user)
        if tenant is None:
            return Client.objects.none()

        base_qs = Client.objects.filter(professional_id=user_id, tenant_id=tenant.id)

        # Promoção oportunística: garante que o banco reflita o status real antes de anotar.
        user_appts = Appointment.objects.filter(professional_id=user_id)
        promote_scheduled_to_ongoing(base_qs=user_appts)
        promote_overdue_scheduled_to_pending(base_qs=user_appts)

        # Enriquecimento: próximo compromisso (em andamento ou futuro), exclui cancelados.
        # 'ongoing' (start_at < now) tem prioridade sobre futuros (start_at >= now).
        now = timezone.now()
        appt_qs = (
            Appointment.objects.filter(
                professional_id=user_id,
                client_id=OuterRef('pk'),
            )
            .exclude(status=Appointment.Status.CANCELED)
            .filter(Q(start_at__gte=now) | Q(status=Appointment.Status.ONGOING))
            .order_by(
                Case(When(status=Appointment.Status.ONGOING, then=0), default=1, output_field=IntegerField()),
                'start_at',
            )
        )
        last_appt_qs = (
            Appointment.objects.filter(
                professional_id=user_id,
                client_id=OuterRef('pk'),
            )
            .exclude(status=Appointment.Status.CANCELED)
            .filter(start_at__lt=now)
            .order_by('-start_at')
        )

        queryset = base_qs.annotate(
            next_appointment_start_at=Subquery(
                appt_qs.values('start_at')[:1], output_field=DateTimeField()
            ),
            next_appointment_end_at=Subquery(
                appt_qs.values('end_at')[:1], output_field=DateTimeField()
            ),
            next_appointment_title=Subquery(
                appt_qs.values('title')[:1], output_field=CharField()
            ),
            next_appointment_status=Subquery(
                appt_qs.values('status')[:1], output_field=CharField()
            ),
                next_appointment_notes=Subquery(
                    appt_qs.values('notes')[:1], output_field=CharField()
                ),
            next_appointment_id=Subquery(
                appt_qs.values('id')[:1]
            ),
            last_appointment_start_at=Subquery(
                last_appt_qs.values('start_at')[:1], output_field=DateTimeField()
            ),
            last_appointment_end_at=Subquery(
                last_appt_qs.values('end_at')[:1], output_field=DateTimeField()
            ),
            last_appointment_title=Subquery(
                last_appt_qs.values('title')[:1], output_field=CharField()
            ),
            last_appointment_status=Subquery(
                last_appt_qs.values('status')[:1], output_field=CharField()
            ),
            last_appointment_notes=Subquery(
                last_appt_qs.values('notes')[:1], output_field=CharField()
            ),
        )

        if nome:
            queryset = queryset.filter(
                Q(first_name__istartswith=nome) |
                Q(last_name__istartswith=nome)
            )

        return queryset.order_by('first_name')
