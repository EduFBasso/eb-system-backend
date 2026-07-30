import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.clients.models import Client
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership


pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    professional = Professional.objects.create_user(
        email="clients-owner@example.com",
        password="secret123",
        first_name="Owner",
        last_name="Client",
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Owner', slug='tenant-owner')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def other_professional():
    professional = Professional.objects.create_user(
        email="clients-other@example.com",
        password="secret123",
        first_name="Other",
        last_name="Client",
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Other', slug='tenant-other')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def owner_client(owner):
    return Client.objects.create(
        tenant=owner.tenant_memberships.first().tenant,
        professional=owner,
        first_name="Visible",
        last_name="Client",
        phone="11971000001",
    )


@pytest.fixture
def other_client(other_professional):
    return Client.objects.create(
        tenant=other_professional.tenant_memberships.first().tenant,
        professional=other_professional,
        first_name="Hidden",
        last_name="Client",
        phone="11971000002",
    )


@pytest.fixture
def api_client(owner):
    client = APIClient()
    token = AccessToken.for_user(owner)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


def test_professional_lists_only_own_clients(api_client, owner_client, other_client):
    response = api_client.get("/register/clients/")

    assert response.status_code == 200, response.content
    payload = response.json()
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    ids = {item["id"] for item in rows}
    assert owner_client.id in ids
    assert other_client.id not in ids


def test_professional_cannot_read_other_professional_client(api_client, other_client):
    response = api_client.get(f"/register/clients/{other_client.id}/")

    assert response.status_code == 404


def test_professional_cannot_update_other_professional_client(api_client, other_client):
    response = api_client.patch(
        f"/register/clients/{other_client.id}/",
        {"first_name": "Changed"},
        format="json",
    )

    assert response.status_code == 404
    other_client.refresh_from_db()
    assert other_client.first_name == "Hidden"


def test_client_create_ignores_payload_professional_and_uses_authenticated_user(
    api_client,
    owner,
    other_professional,
):
    response = api_client.post(
        "/register/clients/",
        {
            "professional": other_professional.id,
            "first_name": "New",
            "last_name": "Client",
            "phone": "11971000003",
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    created = Client.objects.get(id=response.json()["id"])
    assert created.professional_id == owner.id
    assert created.professional_id != other_professional.id