from unittest.mock import Mock, patch

import pytest
from apps.authentication.models import Professional, Tenant, TenantMembership
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def test_bakery_lookup_cep_returns_address_data():
    client = APIClient()

    response_payload = {
        'logradouro': 'Avenida Paulista',
        'bairro': 'Bela Vista',
        'localidade': 'São Paulo',
        'uf': 'SP',
    }

    mocked_response = Mock()
    mocked_response.raise_for_status.return_value = None
    mocked_response.json.return_value = response_payload

    with patch('utils.cep_lookup.requests.get', return_value=mocked_response) as mocked_get:
        response = client.post(
            '/api/v1/bakery/customers/lookup-cep/',
            {'zip_code': '01310-100'},
            format='json',
        )

    assert response.status_code == 200
    assert response.data == {
        'street': 'Avenida Paulista',
        'neighborhood': 'Bela Vista',
        'city': 'São Paulo',
        'state': 'SP',
        'zip_code': '01310100',
    }
    mocked_get.assert_called_once_with('https://viacep.com.br/ws/01310100/json/', timeout=10)


def test_bakery_lookup_cep_rejects_invalid_zip():
    client = APIClient()

    response = client.post(
        '/api/v1/bakery/customers/lookup-cep/',
        {'zip_code': '123'},
        format='json',
    )

    assert response.status_code == 400
    assert response.data['detail'] == 'CEP não encontrado'


def test_bakery_register_customer_uses_admin_token_and_creates_pending_customer():
    tenant = Tenant.objects.create(
        name='Bakery Tenant',
        slug='bakery-tenant',
        capabilities={'bakery': True},
        is_active=True,
    )
    admin = Professional.objects.create_user(
        email='admin@bakery.test',
        password='secret123',
        first_name='Admin',
        last_name='Bakery',
        is_staff=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=admin,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.post(
        '/api/v1/bakery/customers/register/',
        {
            'nickname': 'Cliente Teste',
            'customer_type': 'PF',
            'cpf': '11122233344',
            'phone': '11999999991',
            'zip_code': '01310100',
            'street': 'Avenida Paulista',
            'number': '1000',
            'neighborhood': 'Bela Vista',
            'city': 'São Paulo',
            'state': 'SP',
        },
        format='json',
    )

    assert response.status_code == 201
    assert response.data['nickname'] == 'Cliente Teste'
    assert response.data['status'] == 'PENDENTE'
    assert response.data['tenant'] == tenant.id
    assert response.data['user'] != admin.id


def test_bakery_register_customer_allows_multiple_customers_for_same_admin_tenant():
    tenant = Tenant.objects.create(
        name='Bakery Tenant 2',
        slug='bakery-tenant-2',
        capabilities={'bakery': True},
        is_active=True,
    )
    admin = Professional.objects.create_user(
        email='admin2@bakery.test',
        password='secret123',
        first_name='Admin',
        last_name='Bakery',
        is_staff=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=admin,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    payload_a = {
        'nickname': 'Cliente A',
        'customer_type': 'PF',
        'cpf': '11122233355',
        'phone': '11999999901',
        'zip_code': '01310100',
        'street': 'Avenida Paulista',
        'number': '1000',
        'neighborhood': 'Bela Vista',
        'city': 'São Paulo',
        'state': 'SP',
    }
    payload_b = {
        'nickname': 'Cliente B',
        'customer_type': 'PF',
        'cpf': '11122233366',
        'phone': '11999999902',
        'zip_code': '01310100',
        'street': 'Avenida Paulista',
        'number': '1001',
        'neighborhood': 'Bela Vista',
        'city': 'São Paulo',
        'state': 'SP',
    }

    response_a = client.post('/api/v1/bakery/customers/register/', payload_a, format='json')
    response_b = client.post('/api/v1/bakery/customers/register/', payload_b, format='json')

    assert response_a.status_code == 201
    assert response_b.status_code == 201
    assert response_a.data['tenant'] == tenant.id
    assert response_b.data['tenant'] == tenant.id
    assert response_a.data['user'] != response_b.data['user']


def test_bakery_approve_customer_returns_json_and_updates_status():
    tenant = Tenant.objects.create(
        name='Bakery Tenant 3',
        slug='bakery-tenant-3',
        capabilities={'bakery': True},
        is_active=True,
    )
    admin = Professional.objects.create_user(
        email='admin3@bakery.test',
        password='secret123',
        first_name='Admin',
        last_name='Bakery',
        is_staff=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=admin,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    register_response = client.post(
        '/api/v1/bakery/customers/register/',
        {
            'nickname': 'Cliente Aprovar',
            'customer_type': 'PF',
            'cpf': '11122233377',
            'phone': '11999999903',
            'zip_code': '01310100',
            'street': 'Avenida Paulista',
            'number': '1000',
            'neighborhood': 'Bela Vista',
            'city': 'São Paulo',
            'state': 'SP',
        },
        format='json',
    )
    customer_id = register_response.data['id']

    approve_response = client.post(
        f'/api/v1/bakery/customers/{customer_id}/approve/',
        {
            'credit_limit': '1000.00',
            'admin_password': 'secret123',
        },
        format='json',
    )

    assert approve_response.status_code == 200
    assert approve_response.data['status'] == 'APROVADO'
    assert approve_response.data['credit_limit'] == '1000.00'
    assert approve_response.data['password_plain_text']


def test_bakery_approve_customer_rejects_invalid_admin_password_with_json_error():
    tenant = Tenant.objects.create(
        name='Bakery Tenant 4',
        slug='bakery-tenant-4',
        capabilities={'bakery': True},
        is_active=True,
    )
    admin = Professional.objects.create_user(
        email='admin4@bakery.test',
        password='secret123',
        first_name='Admin',
        last_name='Bakery',
        is_staff=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=admin,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    register_response = client.post(
        '/api/v1/bakery/customers/register/',
        {
            'nickname': 'Cliente Aprovar 2',
            'customer_type': 'PF',
            'cpf': '11122233388',
            'phone': '11999999904',
            'zip_code': '01310100',
            'street': 'Avenida Paulista',
            'number': '1000',
            'neighborhood': 'Bela Vista',
            'city': 'São Paulo',
            'state': 'SP',
        },
        format='json',
    )
    customer_id = register_response.data['id']

    approve_response = client.post(
        f'/api/v1/bakery/customers/{customer_id}/approve/',
        {
            'credit_limit': '1000.00',
            'admin_password': 'senha-errada',
        },
        format='json',
    )

    assert approve_response.status_code == 401
    assert 'detail' in approve_response.data


def test_bakery_customer_can_login_with_nickname_after_approval():
    tenant = Tenant.objects.create(
        name='Bakery Tenant 5',
        slug='bakery-tenant-5',
        capabilities={'bakery': True},
        is_active=True,
    )
    admin = Professional.objects.create_user(
        email='admin5@bakery.test',
        password='secret123',
        first_name='Admin',
        last_name='Bakery',
        is_staff=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=admin,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=admin)
    register_response = client.post(
        '/api/v1/bakery/customers/register/',
        {
            'nickname': 'João',
            'customer_type': 'PF',
            'cpf': '11122233399',
            'phone': '11999999905',
            'zip_code': '01310100',
            'street': 'Avenida Paulista',
            'number': '1000',
            'neighborhood': 'Bela Vista',
            'city': 'São Paulo',
            'state': 'SP',
        },
        format='json',
    )
    customer_id = register_response.data['id']

    approve_response = client.post(
        f'/api/v1/bakery/customers/{customer_id}/approve/',
        {
            'credit_limit': '1000.00',
            'admin_password': 'secret123',
            'password': 'XmXHYvp6',
        },
        format='json',
    )
    assert approve_response.status_code == 200

    anon_client = APIClient()
    login_response = anon_client.post(
        '/api/v1/auth/bakery/login/',
        {
            'email': 'João',
            'password': 'XmXHYvp6',
        },
        format='json',
    )

    assert login_response.status_code == 200
    assert login_response.data['customer']['nickname'] == 'João'
    assert login_response.data['customer']['status'] == 'APROVADO'
    assert 'access' in login_response.data
    assert 'refresh' in login_response.data


def test_bakery_customer_pending_cannot_login_with_nickname():
    tenant = Tenant.objects.create(
        name='Bakery Tenant 6',
        slug='bakery-tenant-6',
        capabilities={'bakery': True},
        is_active=True,
    )
    admin = Professional.objects.create_user(
        email='admin6@bakery.test',
        password='secret123',
        first_name='Admin',
        last_name='Bakery',
        is_staff=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=admin,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=admin)
    register_response = client.post(
        '/api/v1/bakery/customers/register/',
        {
            'nickname': 'Pendente',
            'customer_type': 'PF',
            'cpf': '11122233400',
            'phone': '11999999906',
            'zip_code': '01310100',
            'street': 'Avenida Paulista',
            'number': '1000',
            'neighborhood': 'Bela Vista',
            'city': 'São Paulo',
            'state': 'SP',
        },
        format='json',
    )
    assert register_response.status_code == 201

    anon_client = APIClient()
    login_response = anon_client.post(
        '/api/v1/auth/bakery/login/',
        {
            'email': 'Pendente',
            'password': 'qualquer',
        },
        format='json',
    )

    assert login_response.status_code == 400
