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
        email='ongoing@example.com', password='x', first_name='On', last_name='Going'
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Ongoing', slug='tenant-ongoing')
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


def make_ongoing(professional, client):
    now = timezone.now()
    start = now - timezone.timedelta(minutes=10)
    end = now + timezone.timedelta(minutes=20)
    return Appointment.objects.create(
        tenant=client.tenant,
        professional=professional,
        client=client,
        title='Sessão em andamento',
        start_at=start,
        end_at=end,
        status=Appointment.Status.SCHEDULED,
    )


def test_edit_client_allowed_during_ongoing(api, professional):
    tenant = professional.tenant_memberships.first().tenant
    cli = Client.objects.create(
        tenant=tenant,
        professional=professional,
        first_name='Ana', last_name='Teste', phone='11970000000'
    )
    make_ongoing(professional, cli)

    # Editar dados do cliente (ex.: telefone) deve ser permitido
    r = api.patch(f'/register/clients/{cli.id}/', {
        'phone': '11970000001',
        'city': 'Campinas'
    }, format='json')
    assert r.status_code in (200, 202), r.content
    body = r.json()
    assert body['phone'] == '11970000001'
    assert body.get('city', '') in ('Campinas', '')


def test_create_another_client_allowed_during_ongoing(api, professional):
    tenant = professional.tenant_memberships.first().tenant
    cli = Client.objects.create(
        tenant=tenant,
        professional=professional,
        first_name='Ana', last_name='Teste', phone='11970000010'
    )
    make_ongoing(professional, cli)

    # Criar outro cliente deve ser permitido normalmente
    r = api.post('/register/clients/', {
        'first_name': 'Bruno', 'last_name': 'Silva', 'phone': '11970000011'
    }, format='json')
    assert r.status_code == 201, r.content
    body = r.json()
    assert body['first_name'] == 'Bruno'
    assert body['phone'] == '11970000011'
