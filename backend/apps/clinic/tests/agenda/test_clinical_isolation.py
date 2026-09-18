import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.agenda import ClinicalRecord, Encounter
from apps.clinic.models.clients import Client


pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    professional = Professional.objects.create_user(
        email="clinical-owner@example.com",
        password="secret123",
        first_name="Clinical",
        last_name="Owner",
    )
    tenant = Tenant.objects.create(
        name="Clinical Owner Tenant",
        slug="clinical-owner-tenant",
        ecosystem="clinic",
        is_active=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def other_client():
    other_professional = Professional.objects.create_user(
        email="clinical-other@example.com",
        password="secret123",
        first_name="Clinical",
        last_name="Other",
    )
    other_tenant = Tenant.objects.create(
        name="Clinical Other Tenant",
        slug="clinical-other-tenant",
        ecosystem="clinic",
        is_active=True,
    )
    TenantMembership.objects.create(
        tenant=other_tenant,
        professional=other_professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return Client.objects.create(
        tenant=other_tenant,
        first_name="Other",
        last_name="Client",
        phone="11972000003",
    )


@pytest.fixture
def api_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def test_professional_cannot_create_encounter_for_other_tenant_client(api_client, other_client):
    response = api_client.post(
        "/agenda/encounters/",
        {"client": other_client.id, "chief_complaint": "Cross tenant"},
        format="json",
    )

    assert response.status_code == 400, response.content
    assert "client" in response.json()
    assert not Encounter.objects.filter(client=other_client).exists()


def test_professional_cannot_create_record_for_other_tenant_client(api_client, other_client):
    response = api_client.post(
        "/agenda/clinical-records/",
        {
            "client": other_client.id,
            "record_type": ClinicalRecord.RecordType.NOTE,
            "content": "Cross tenant",
        },
        format="json",
    )

    assert response.status_code == 400, response.content
    assert "client" in response.json()
    assert not ClinicalRecord.objects.filter(client=other_client).exists()


def test_professional_cannot_read_or_update_other_tenant_clinical_data(api_client, other_client):
    other_professional = other_client.tenant.memberships.get().professional
    encounter = Encounter.objects.create(
        tenant=other_client.tenant,
        professional=other_professional,
        client=other_client,
        chief_complaint="Other tenant",
    )
    record = ClinicalRecord.objects.create(
        tenant=other_client.tenant,
        professional=other_professional,
        client=other_client,
        encounter=encounter,
        record_type=ClinicalRecord.RecordType.NOTE,
        content="Other tenant record",
    )

    for path in (
        f"/agenda/encounters/{encounter.id}/",
        f"/agenda/clinical-records/{record.id}/",
    ):
        assert api_client.get(path).status_code == 404
        assert api_client.patch(path, {"notes": "Changed"}, format="json").status_code == 404

    assert api_client.get("/agenda/encounters/").json() == []
    assert api_client.get("/agenda/clinical-records/").json() == []