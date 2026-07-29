import json

from django.db.models import Q, OuterRef, Subquery, DateTimeField, CharField, Case, When, IntegerField
from django.utils.dateparse import parse_date
from django.utils import timezone
from apps.agenda.models import Appointment
from apps.agenda.state_utils import promote_scheduled_to_ongoing, promote_overdue_scheduled_to_pending
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db import IntegrityError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from apps.clients.models import Client
from apps.clients.serializers import ClientSerializer, ClientBasicSerializer
from apps.anamnesis.models import AnamneseBase


ANAMNESIS_LINK_SALT = 'anamnesis-link-v1'
PUBLIC_CLIENT_FIELDS = (
    'first_name',
    'last_name',
    'email',
    'phone',
    'profession',
    'document_type',
    'document_number',
    'sex',
    'marital_status',
    'address',
    'neighborhood',
    'city',
    'state',
    'postal_code',
    'address_number',
    'address_complement',
    'date_of_birth',
)
PUBLIC_ANAMNESE_BASE_FIELDS = (
    'takes_medication',
    'had_surgery',
    'is_pregnant',
    'pain_sensitivity',
    'clinical_history',
    'sport_activity',
    'academic_activity',
)
PODOLOGIA_BLOCK_MESSAGE = 'Campos de anamnese podologia não são permitidos neste endpoint.'
LINK_EXPIRED_MESSAGE = 'Link expirado'


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

    def _decode_anamnesis_token(self, token):
        signer = TimestampSigner(salt=ANAMNESIS_LINK_SALT)
        try:
            raw_payload = signer.unsign(token, max_age=3600)
            payload = json.loads(raw_payload)
        except (BadSignature, SignatureExpired, json.JSONDecodeError, TypeError, ValueError):
            return None

        if not isinstance(payload, dict):
            return None

        if not payload.get('client_id') or not payload.get('tenant_id') or not payload.get('professional_id'):
            return None

        return payload

    @staticmethod
    def _parse_public_date_of_birth(value):
        if value in (None, ''):
            return None
        if not isinstance(value, str):
            raise ValidationError({'date_of_birth': ['Data de nascimento inválida.']})

        raw = value.strip()
        if not raw:
            return None

        if '/' in raw:
            chunks = raw.split('/')
            if len(chunks) == 3:
                day, month, year = chunks
                raw = f'{year}-{month}-{day}'

        parsed = parse_date(raw)
        if parsed is None:
            raise ValidationError({'date_of_birth': ['Data de nascimento inválida.']})
        return parsed

    @action(detail=True, methods=['post'], url_path='generate-anamnesis-token')
    def generate_anamnesis_token(self, request, pk=None):
        client = self.get_object()
        signer = TimestampSigner(salt=ANAMNESIS_LINK_SALT)
        payload = {
            'client_id': client.id,
            'tenant_id': client.tenant_id,
            'professional_id': client.professional_id,
        }
        token = signer.sign(json.dumps(payload, separators=(',', ':')))
        return Response({'token': token, 'expires_in': 3600}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['get', 'post'],
        url_path='validate-anamnesis-token',
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def validate_anamnesis_token(self, request):
        token = request.data.get('token') or request.query_params.get('token')
        if not token:
            return Response({'detail': LINK_EXPIRED_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        payload = self._decode_anamnesis_token(token)
        if payload is None:
            return Response({'detail': LINK_EXPIRED_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        client_id = payload['client_id']
        tenant_id = payload['tenant_id']
        professional_id = payload['professional_id']

        client = Client.objects.filter(
            id=client_id,
            tenant_id=tenant_id,
            professional_id=professional_id,
        ).first()
        if client is None:
            return Response({'detail': LINK_EXPIRED_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        base = AnamneseBase.objects.filter(
            client=client,
            tenant_id=tenant_id,
            professional_id=professional_id,
        ).first()

        client_payload = {
            'id': client.id,
            'full_name': f'{client.first_name} {client.last_name}'.strip(),
        }
        for field in PUBLIC_CLIENT_FIELDS:
            client_payload[field] = getattr(client, field, None)

        base_payload = {}
        if base is not None:
            for field in PUBLIC_ANAMNESE_BASE_FIELDS:
                base_payload[field] = getattr(base, field, None)

        return Response(
            {
                'client': {
                    **client_payload,
                    'anamnese_base': base_payload,
                }
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='submit-public-anamnesis',
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def submit_public_anamnesis(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'detail': LINK_EXPIRED_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        if 'anamnese_podologia' in request.data:
            return Response({'detail': PODOLOGIA_BLOCK_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        payload = self._decode_anamnesis_token(token)
        if payload is None:
            return Response({'detail': LINK_EXPIRED_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        client = Client.objects.filter(
            id=payload['client_id'],
            tenant_id=payload['tenant_id'],
            professional_id=payload['professional_id'],
        ).first()
        if client is None:
            return Response({'detail': LINK_EXPIRED_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        anamnese_base_data = request.data.get('anamnese_base')
        if anamnese_base_data is None:
            anamnese_base_data = {}
        if not isinstance(anamnese_base_data, dict):
            return Response(
                {'detail': 'anamnese_base inválida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_updates = {}
        for field in PUBLIC_CLIENT_FIELDS:
            if field not in request.data:
                continue
            value = request.data.get(field)
            if field == 'date_of_birth':
                try:
                    client_updates[field] = self._parse_public_date_of_birth(value)
                except ValidationError as exc:
                    return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
                continue

            if field == 'phone' and isinstance(value, str):
                digits = ''.join(ch for ch in value if ch.isdigit())
                client_updates[field] = digits or None
                continue

            if isinstance(value, str):
                value = value.strip()
            client_updates[field] = value

        base_updates = {
            key: anamnese_base_data[key]
            for key in PUBLIC_ANAMNESE_BASE_FIELDS
            if key in anamnese_base_data
        }

        try:
            with transaction.atomic():
                for key, value in client_updates.items():
                    setattr(client, key, value)
                if client_updates:
                    client.save(update_fields=list(client_updates.keys()) + ['updated_at'])

                if base_updates:
                    AnamneseBase.objects.update_or_create(
                        client=client,
                        tenant_id=payload['tenant_id'],
                        professional_id=payload['professional_id'],
                        defaults=base_updates,
                    )
        except IntegrityError:
            return Response(
                {'detail': 'Não foi possível salvar os dados enviados.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        full_name = f'{client.first_name} {client.last_name}'.strip()
        return Response(
            {
                'detail': 'Anamnese enviada com sucesso',
                'client': {
                    'id': client.id,
                    'full_name': full_name,
                },
            },
            status=status.HTTP_200_OK,
        )



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
