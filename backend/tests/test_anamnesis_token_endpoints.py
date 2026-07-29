import pytest
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.anamnesis.models import AnamneseBase, AnamnesePodologia
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership


pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    return Professional.objects.create_user(
        email='anamnese-owner@example.com',
        password='secret123',
        first_name='Owner',
        last_name='Tester',
    )


@pytest.fixture
def tenant(professional):
    t = Tenant.objects.create(name='Tenant Teste', slug='tenant-teste')
    TenantMembership.objects.create(
        tenant=t,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return t


@pytest.fixture
def auth_client(professional):
    client = APIClient()
    client.force_authenticate(user=professional)
    return client


@pytest.fixture
def client_obj(auth_client):
    response = auth_client.post(
        '/register/clients/',
        {
            'first_name': 'Maria',
            'last_name': 'Paciente',
            'phone': '11999999998',
        },
        format='json',
    )
    assert response.status_code == 201, response.content
    return Client.objects.get(pk=response.data['id'])


def test_generate_and_validate_anamnesis_token(auth_client, client_obj):
    generate_response = auth_client.post(
        f'/register/clients/{client_obj.id}/generate-anamnesis-token/'
    )

    assert generate_response.status_code == 200, generate_response.content
    token = generate_response.data.get('token')
    assert token

    public_client = APIClient()
    validate_response = public_client.get(
        '/register/clients/validate-anamnesis-token/',
        {'token': token},
    )

    assert validate_response.status_code == 200, validate_response.content
    assert validate_response.data['client']['id'] == client_obj.id
    assert validate_response.data['client']['first_name'] == 'Maria'
    assert validate_response.data['client']['full_name'] == 'Maria Paciente'


def test_validate_anamnesis_token_returns_expired_message_for_invalid_token():
    public_client = APIClient()

    response = public_client.post(
        '/register/clients/validate-anamnesis-token/',
        {'token': 'token-invalido'},
        format='json',
    )

    assert response.status_code == 400, response.content
    assert response.data['detail'] == 'Link expirado'


def test_generate_anamnesis_token_endpoint_requires_authentication(client_obj):
    public_client = APIClient()

    response = public_client.post(
        f'/register/clients/{client_obj.id}/generate-anamnesis-token/'
    )

    assert response.status_code == 401, response.content


def test_submit_public_anamnesis_updates_client_and_base(auth_client, client_obj):
    generate_response = auth_client.post(
        f'/register/clients/{client_obj.id}/generate-anamnesis-token/'
    )
    assert generate_response.status_code == 200, generate_response.content
    token = generate_response.data['token']

    public_client = APIClient()
    response = public_client.post(
        '/register/clients/submit-public-anamnesis/',
        {
            'token': token,
            'first_name': 'Maria Atualizada',
            'address': 'Rua Nova, 123',
            'city': 'Limeira',
            'state': 'SP',
            'anamnese_base': {
                'takes_medication': 'Sim: Losartana',
                'had_surgery': 'Não',
                'pain_sensitivity': 'Moderada',
                'clinical_history': 'Hipertensão',
                'sport_activity': 'Leve',
            },
        },
        format='json',
    )

    assert response.status_code == 200, response.content
    client_obj.refresh_from_db()
    assert client_obj.first_name == 'Maria Atualizada'
    assert client_obj.address == 'Rua Nova, 123'

    base = AnamneseBase.objects.get(
        client=client_obj,
        tenant=client_obj.tenant,
        professional=client_obj.professional,
    )
    assert base.takes_medication == 'Sim: Losartana'
    assert base.clinical_history == 'Hipertensão'


def test_submit_public_anamnesis_blocks_podologia_payload(auth_client, client_obj):
    generate_response = auth_client.post(
        f'/register/clients/{client_obj.id}/generate-anamnesis-token/'
    )
    assert generate_response.status_code == 200, generate_response.content
    token = generate_response.data['token']

    public_client = APIClient()
    response = public_client.post(
        '/register/clients/submit-public-anamnesis/',
        {
            'token': token,
            'anamnese_base': {'clinical_history': 'Diabetes'},
            'anamnese_podologia': {'footwear_used': 'Tênis'},
        },
        format='json',
    )

    assert response.status_code == 400, response.content
    assert 'podologia' in response.data['detail'].lower()
    assert not AnamnesePodologia.objects.filter(
        client=client_obj,
        tenant=client_obj.tenant,
        professional=client_obj.professional,
    ).exists()
