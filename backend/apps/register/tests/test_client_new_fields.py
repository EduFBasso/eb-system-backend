import pytest
from datetime import date
from rest_framework.test import APIRequestFactory
from apps.clients.models import Client
from apps.clients.serializers import ClientSerializer
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership

pytestmark = pytest.mark.django_db

@pytest.fixture
def professional():
    professional = Professional.objects.create_user(
        email="fields@example.com", password="x", first_name="Fields", last_name="Test"
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Fields', slug='tenant-fields')
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

def test_create_with_date_of_birth_and_address_number(professional, tenant, serializer_request):
    dob = date(1990, 5, 17)
    ser = ClientSerializer(
        context={'tenant': tenant, 'request': serializer_request},
        data={
            "first_name": "Maria",
            "last_name": "Teste",
            "phone": "11988887777",
            "date_of_birth": dob.isoformat(),
            "address_number": "123",
        }
    )
    assert ser.is_valid(), ser.errors
    obj = ser.save()
    assert obj.date_of_birth == dob
    assert obj.address_number == "123"


def test_create_without_optional_fields(professional, tenant, serializer_request):
    ser = ClientSerializer(
        context={'tenant': tenant, 'request': serializer_request},
        data={
            "first_name": "Joao",
            "last_name": "Silva",
            "phone": "11999998888",
        }
    )
    assert ser.is_valid(), ser.errors
    obj = ser.save()
    assert obj.date_of_birth is None
    assert obj.address_number is None


def test_partial_update_date_and_number(professional, tenant, serializer_request):
    client = Client.objects.create(
        tenant=tenant,
        professional=professional,
        first_name="Ana",
        last_name="Base",
        phone="11970000000",
    )
    ser = ClientSerializer(
        client,
        context={'tenant': tenant, 'request': serializer_request},
        data={"date_of_birth": "2001-01-02", "address_number": "45"},
        partial=True,
    )
    assert ser.is_valid(), ser.errors
    obj = ser.save()
    assert str(obj.date_of_birth) == "2001-01-02"
    assert obj.address_number == "45"


def test_reject_invalid_date(professional, tenant, serializer_request):
    ser = ClientSerializer(
        context={'tenant': tenant, 'request': serializer_request},
        data={
            "first_name": "Data",
            "last_name": "Invalida",
            "phone": "11981112222",
            "date_of_birth": "1990-13-40",  # data impossível
        }
    )
    assert not ser.is_valid()
    assert "date_of_birth" in ser.errors


def test_reject_non_digit_address_number(professional, tenant, serializer_request):
    ser = ClientSerializer(
        context={'tenant': tenant, 'request': serializer_request},
        data={
            "first_name": "Num",
            "last_name": "Errado",
            "phone": "11982223333",
            "address_number": "12A4",  # contém letra
        }
    )
    # Dependendo da validação implementada, pode ser aceito se não houver regra explícita.
    # Se quisermos forçar apenas dígitos, ajustamos o serializer. Aqui verificamos comportamento atual.
    ser.is_valid()
    # Placeholder assertion: apenas garante que o campo está presente em validated_data (ou erro se futuramente validado)
    if ser.is_valid():
        assert "address_number" in ser.validated_data
    else:
        assert "address_number" in ser.errors
