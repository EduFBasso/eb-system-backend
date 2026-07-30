import pytest
from rest_framework.test import APIRequestFactory
from apps.clients.serializers import ClientSerializer
from apps.clients.models import Client
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership


@pytest.fixture
def professional(db):
    professional = Professional.objects.create_user(
        email="pro2@example.com", password="x", first_name="Pro", last_name="Two"
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Pro Two', slug='tenant-pro-two')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def tenant(professional):
    return professional.tenant_memberships.first().tenant


@pytest.fixture
def serializer_request(professional):
    request = APIRequestFactory().post('/register/clients/')
    request.user = professional
    return request


def test_phone_normalization(db, professional, tenant, serializer_request):
    data = {
        'first_name': 'Ana',
        'last_name': 'Silva',
        'phone': '(19) 98888-7777',
    }
    ser = ClientSerializer(
        data=data,
        context={'tenant': tenant, 'request': serializer_request},
    )
    assert ser.is_valid(), ser.errors
    obj = ser.save()
    assert obj.phone == '19988887777'


@pytest.mark.parametrize('invalid', ['123', '999', 'abcdefghij', '123456789012'])
def test_phone_invalid_lengths(db, professional, tenant, serializer_request, invalid):
    data = {
        'first_name': 'João',
        'last_name': 'Teste',
        'phone': invalid,
    }
    ser = ClientSerializer(
        data=data,
        context={'tenant': tenant, 'request': serializer_request},
    )
    assert not ser.is_valid()
    assert 'phone' in ser.errors


def test_optional_fields_blank(db, professional, tenant, serializer_request):
    data = {
        'first_name': 'Bia',
        'last_name': 'Oliveira',
        'phone': '19977776666',
        'city': '',
        'state': '',
    }
    ser = ClientSerializer(
        data=data,
        context={'tenant': tenant, 'request': serializer_request},
    )
    assert ser.is_valid(), ser.errors
    obj = ser.save()
    assert obj.city == '' or obj.city is None
    assert obj.state == '' or obj.state is None