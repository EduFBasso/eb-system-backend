import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership


@pytest.mark.django_db
def test_clinic_authentication_uses_password_without_totp():
    professional = Professional.objects.create_user(
        email="podologia@example.com",
        password="senha-segura-123",
        first_name="Profissional",
        last_name="Podologia",
    )
    tenant = Tenant.objects.create(
        name="Consultorio Podologia",
        slug="consultorio-podologia-auth",
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={"clinic": True, "podologia": True},
        is_active=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
        is_active=True,
    )

    response = APIClient().post(
        "/token/",
        {"email": professional.email, "password": "senha-segura-123"},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.data["professional"]["capabilities"] == {
        "clinic": True,
        "podologia": True,
    }
    assert "totp_secret" not in {field.name for field in Professional._meta.fields}


@pytest.mark.django_db
def test_admin_creates_professional_without_totp_contract():
    admin = Professional.objects.create_superuser(
        email="admin@example.com",
        password="senha-admin-123",
        first_name="Admin",
        last_name="Sistema",
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.post(
        "/register/auth/professional-create/",
        {
            "email": "odonto@example.com",
            "password": "senha-profissional-123",
            "first_name": "Profissional",
            "last_name": "Odonto",
            "phone": "19999999999",
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.data["professional"]["email"] == "odonto@example.com"
    assert "secret" not in response.data
    assert "otpauth_uri" not in response.data


@pytest.mark.django_db
def test_totp_route_is_unavailable():
    response = APIClient().post("/register/auth/totp/verify/", format="json")

    assert response.status_code == 404