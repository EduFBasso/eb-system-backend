import pytest
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.register.models import Professional


pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return Professional.objects.create_user(
        email="clients-owner@example.com",
        password="secret123",
        first_name="Owner",
        last_name="Client",
    )


@pytest.fixture
def other_professional():
    return Professional.objects.create_user(
        email="clients-other@example.com",
        password="secret123",
        first_name="Other",
        last_name="Client",
    )


@pytest.fixture
def owner_client(owner):
    return Client.objects.create(
        professional=owner,
        first_name="Visible",
        last_name="Client",
        phone="11971000001",
    )


@pytest.fixture
def other_client(other_professional):
    return Client.objects.create(
        professional=other_professional,
        first_name="Hidden",
        last_name="Client",
        phone="11971000002",
    )


@pytest.fixture
def api_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def test_professional_lists_only_own_clients(api_client, owner_client, other_client):
    response = api_client.get("/register/clients/")

    assert response.status_code == 200, response.content
    ids = {item["id"] for item in response.json()}
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