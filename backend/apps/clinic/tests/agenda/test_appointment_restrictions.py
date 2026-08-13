import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.agenda import Appointment

pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    pro = Professional.objects.create_user(email='restri@example.com', password='x', first_name='Res', last_name='Tri')
    pro.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Restri', slug='tenant-restri')
    TenantMembership.objects.create(tenant=tenant, professional=pro, role=TenantMembership.Role.OWNER, is_active=True)
    return pro


@pytest.fixture
def other_professional():
    pro = Professional.objects.create_user(email='other@example.com', password='x', first_name='Other', last_name='Pro')
    pro.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Other Restri', slug='tenant-other-restri')
    TenantMembership.objects.create(tenant=tenant, professional=pro, role=TenantMembership.Role.OWNER, is_active=True)
    return pro


@pytest.fixture
def client1(professional):
    return Client.objects.create(tenant=professional.tenant_memberships.first().tenant, first_name='Cli', last_name='One', phone='11970000001')


@pytest.fixture
def client2(professional):
    return Client.objects.create(tenant=professional.tenant_memberships.first().tenant, first_name='Cli', last_name='Two', phone='11970000002')


@pytest.fixture
def api_client(professional):
    c = APIClient()
    c.force_authenticate(user=professional)
    return c


def make_future():
    base = timezone.now() + timezone.timedelta(hours=2)
    return base, base + timezone.timedelta(minutes=30)


def test_client_cannot_change(api_client, professional, client1, client2):
    start, end = make_future()
    r = api_client.post('/agenda/appointments/', {
        'client': client1.id,
        'title': 'Sessão',
        'visit_type': 'consulta',
        'start_at': start.isoformat(),
        'end_at': end.isoformat(),
    }, format='json')
    assert r.status_code == 201, r.content
    appt_id = r.json()['id']

    # Tentativa de alterar client via PATCH
    r2 = api_client.patch(f'/agenda/appointments/{appt_id}/', {
        'client': client2.id
    }, format='json')
    assert r2.status_code == 400
    body_lower = str(r2.data).lower()
    # Aceita a mensagem antiga (específica) ou a nova mensagem de bloqueio geral de edição
    assert (
        'cliente não pode ser alterado' in body_lower
        or 'edição de compromissos está temporariamente bloqueada' in body_lower
    )


def test_delete_is_blocked(api_client, client1):
    start, end = make_future()
    r = api_client.post('/agenda/appointments/', {
        'client': client1.id,
        'title': 'Sessão',
        'visit_type': 'consulta',
        'start_at': start.isoformat(),
        'end_at': end.isoformat(),
    }, format='json')
    appt_id = r.json()['id']
    del_res = api_client.delete(f'/agenda/appointments/{appt_id}/')
    assert del_res.status_code == 405
    assert 'Exclusão não permitida' in str(del_res.data)

    get_res = api_client.get(f'/agenda/appointments/{appt_id}/')
    assert get_res.status_code == 200


def test_cancel_action(api_client, client1):
    start, end = make_future()
    r = api_client.post('/agenda/appointments/', {
        'client': client1.id,
        'title': 'Sessão',
        'visit_type': 'consulta',
        'start_at': start.isoformat(),
        'end_at': end.isoformat(),
    }, format='json')
    appt_id = r.json()['id']
    cancel = api_client.post(f'/agenda/appointments/{appt_id}/cancel/')
    assert cancel.status_code == 200, cancel.content
    assert cancel.json()['status'] == 'canceled'

    # Repetir cancel deve retornar 200 idempotente
    cancel2 = api_client.post(f'/agenda/appointments/{appt_id}/cancel/')
    assert cancel2.status_code == 200

