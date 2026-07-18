import pytest
from rest_framework.test import APIClient

from apps.register.models import Professional


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def ordinary_professional():
    return Professional.objects.create_user(
        email="ordinary@example.com",
        password="secret123",
        first_name="Ordinary",
        last_name="User",
    )


@pytest.fixture
def managed_professional():
    return Professional.objects.create_user(
        email="managed@example.com",
        password="secret123",
        first_name="Managed",
        last_name="User",
    )


@pytest.fixture
def manager_professional():
    return Professional.objects.create_user(
        email="manager@example.com",
        password="secret123",
        first_name="Manager",
        last_name="User",
        can_manage_professionals=True,
    )


def test_ordinary_professional_cannot_list_professional_directory(
    api_client,
    ordinary_professional,
    managed_professional,
):
    api_client.force_authenticate(user=ordinary_professional)

    response = api_client.get("/register/professionals/")

    assert response.status_code == 403


def test_ordinary_professional_cannot_retrieve_another_professional(
    api_client,
    ordinary_professional,
    managed_professional,
):
    api_client.force_authenticate(user=ordinary_professional)

    response = api_client.get(f"/register/professionals/{managed_professional.id}/")

    assert response.status_code == 403


def test_professional_manager_can_list_professional_directory(
    api_client,
    manager_professional,
    managed_professional,
):
    api_client.force_authenticate(user=manager_professional)

    response = api_client.get("/register/professionals/")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert manager_professional.id in ids
    assert managed_professional.id in ids


def test_ordinary_professional_keeps_self_service_profile_endpoint(
    api_client,
    ordinary_professional,
):
    api_client.force_authenticate(user=ordinary_professional)

    response = api_client.get("/register/professionals/me/")

    assert response.status_code == 200
    assert response.json()["id"] == ordinary_professional.id