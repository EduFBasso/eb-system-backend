import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import SystemUser, Tenant, TenantMembership


pytestmark = pytest.mark.django_db


def _client_with_token(professional, *, tenant_id, ecosystem):
    token = AccessToken.for_user(professional)
    if tenant_id is not None:
        token["tenant_id"] = tenant_id
    if ecosystem is not None:
        token["ecosystem"] = ecosystem

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def test_bakery_token_cannot_access_clinic_agenda():
    professional = SystemUser.objects.create_user(
        email="bakery-agenda@example.com",
        password="secret123",
    )
    tenant = Tenant.objects.create(
        name="Padaria Agenda",
        slug="padaria-agenda",
        ecosystem=Tenant.Ecosystem.BAKERY,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        is_active=True,
    )

    response = _client_with_token(
        professional,
        tenant_id=tenant.id,
        ecosystem=Tenant.Ecosystem.BAKERY,
    ).get("/agenda/appointments/")

    assert response.status_code == 403


def test_clinic_agenda_requires_ecosystem_claim():
    professional = SystemUser.objects.create_user(
        email="missing-ecosystem@example.com",
        password="secret123",
    )
    tenant = Tenant.objects.create(
        name="Clínica Sem Ecosystem",
        slug="clinica-sem-ecosystem",
        ecosystem=Tenant.Ecosystem.CLINIC,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        is_active=True,
    )

    response = _client_with_token(
        professional,
        tenant_id=tenant.id,
        ecosystem=None,
    ).get("/agenda/appointments/")

    assert response.status_code == 403


def test_clinic_agenda_rejects_inactive_membership():
    professional = SystemUser.objects.create_user(
        email="inactive-clinic@example.com",
        password="secret123",
    )
    tenant = Tenant.objects.create(
        name="Clínica Inativa",
        slug="clinica-inativa",
        ecosystem=Tenant.Ecosystem.CLINIC,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        is_active=False,
    )

    response = _client_with_token(
        professional,
        tenant_id=tenant.id,
        ecosystem=Tenant.Ecosystem.CLINIC,
    ).get("/agenda/appointments/")

    assert response.status_code == 403
