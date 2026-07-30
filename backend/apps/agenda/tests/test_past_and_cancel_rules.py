import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from apps.clients.models import Client
from apps.register.models import Professional
from apps.agenda.models import Appointment
from apps.tenancy.models import Tenant, TenantMembership

pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    professional = Professional.objects.create_user(
        email='rules@example.com', password='x', first_name='Regra', last_name='Test'
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Rules', slug='tenant-rules')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def api(professional):
    c = APIClient()
    token = AccessToken.for_user(professional)
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return c


@pytest.fixture
def client_obj(professional):
    tenant = professional.tenant_memberships.first().tenant
    return Client.objects.create(
        tenant=tenant,
        professional=professional,
        first_name='Cliente', last_name='Regras', phone='11981110000'
    )


def make(professional, client, delta_hours_start: int, duration_min=60, status=Appointment.Status.SCHEDULED, title='Sessão'):
    start = (timezone.now() + timezone.timedelta(hours=delta_hours_start)).replace(second=0, microsecond=0)
    end = start + timezone.timedelta(minutes=duration_min)
    return Appointment.objects.create(
        tenant=client.tenant,
        professional=professional,
        client=client,
        title=title,
        start_at=start,
        end_at=end,
        status=status,
    )


def test_past_appointment_cannot_be_edited(api, professional, client_obj):
    past = make(professional, client_obj, -5)
    # tentativa de edição (PATCH) deve falhar (400 ou 403 dependendo da lógica futura)
    r = api.patch(f'/agenda/appointments/{past.id}/', {
        'notes': 'Alterando algo'
    }, format='json')
    # Caso ainda não exista validação explícita, documentamos o esperado: bloquear
    assert r.status_code in (400, 403, 422), r.content


def test_cancel_keeps_record_and_frees_slot(api, professional, client_obj):
    fut = make(professional, client_obj, 2)
    cancel = api.post(f'/agenda/appointments/{fut.id}/cancel/')
    assert cancel.status_code == 200
    # Registro continua existindo
    get_after = api.get(f'/agenda/appointments/{fut.id}/')
    assert get_after.status_code == 200
    assert get_after.json()['status'] == 'canceled'
    # Criar novo no mesmo horário deve ser possível
    new_payload = {
        'client': client_obj.id,
        'title': 'Novo',
        'visit_type': 'avaliacao',
        'start_at': fut.start_at.isoformat(),
        'end_at': fut.end_at.isoformat(),
    }
    r2 = api.post('/agenda/appointments/', new_payload, format='json')
    assert r2.status_code == 201, r2.content


def test_past_and_canceled_not_in_client_basic_next(api, professional, client_obj):
    # passado (scheduled) - deve ser ignorado
    make(professional, client_obj, -3, title='Passado')
    # futuro cancelado - não deve aparecer
    canceled_future = make(professional, client_obj, 5, title='Cancel Futuro')
    canceled_future.status = Appointment.Status.CANCELED
    canceled_future.save(update_fields=['status'])
    # futuro válido - deve ser o escolhido
    future_valid = make(professional, client_obj, 2, title='Futuro OK')
    r = api.get('/register/clients-basic/')
    assert r.status_code == 200
    payload = r.json()
    rows = payload.get('results', []) if isinstance(payload, dict) else payload
    row = rows[0]
    assert row['next_appointment_title'] == 'Futuro OK'
    assert row['next_appointment_id'] == future_valid.id
    # Garantir que não escolheu o cancelado
    assert row['next_appointment_id'] != canceled_future.id
