import pytest
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.odonto.models import DentalArcade, Procedure, Tooth, Surface
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership


pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return Professional.objects.create_user(
        email="odonto-owner@example.com",
        password="secret123",
        first_name="Owner",
        last_name="Odonto",
        specialty="Odontologia",
    )


@pytest.fixture
def other_professional():
    return Professional.objects.create_user(
        email="odonto-other@example.com",
        password="secret123",
        first_name="Other",
        last_name="Odonto",
        specialty="Odontologia",
    )


@pytest.fixture
def podology_professional():
    return Professional.objects.create_user(
        email="podology@example.com",
        password="secret123",
        first_name="Podo",
        last_name="Logy",
        specialty="Podologia",
    )


@pytest.fixture
def odonto_without_capability():
    professional = Professional.objects.create_user(
        email="odonto-without-capability@example.com",
        password="secret123",
        first_name="No",
        last_name="Capability",
        specialty="Odontologia",
    )

    # O onboarding cria tenant/membership automaticamente para novo profissional.
    # Este cenário precisa manter a especialidade odontológica, porém sem capability.
    membership = (
        TenantMembership.objects.select_related("tenant")
        .filter(professional=professional, is_active=True)
        .first()
    )
    if membership:
        membership.tenant.capabilities = {}
        membership.tenant.save(update_fields=["capabilities"])
    else:
        tenant = Tenant.objects.create(
            name="No Capability Tenant",
            slug="no-capability-tenant",
            capabilities={},
        )
        TenantMembership.objects.create(
            tenant=tenant,
            professional=professional,
            role=TenantMembership.Role.MEMBER,
        )

    return professional


@pytest.fixture
def odonto_tenant():
    return Tenant.objects.create(
        name="Odonto Tenant",
        slug="odonto-tenant",
        capabilities={"odonto": True},
    )


@pytest.fixture(autouse=True)
def odonto_memberships(odonto_tenant, owner, other_professional):
    TenantMembership.objects.create(
        tenant=odonto_tenant,
        professional=owner,
        role=TenantMembership.Role.OWNER,
    )
    TenantMembership.objects.create(
        tenant=odonto_tenant,
        professional=other_professional,
        role=TenantMembership.Role.MEMBER,
    )


@pytest.fixture
def owner_client(owner):
    return Client.objects.create(
        professional=owner,
        first_name="Owner",
        last_name="Client",
        phone="11973000001",
    )


@pytest.fixture
def other_client(other_professional):
    return Client.objects.create(
        professional=other_professional,
        first_name="Other",
        last_name="Client",
        phone="11973000002",
    )


@pytest.fixture
def owner_arcade(owner, owner_client):
    return DentalArcade.objects.create(professional=owner, client=owner_client)


@pytest.fixture
def other_arcade(other_professional, other_client):
    return DentalArcade.objects.create(professional=other_professional, client=other_client)


@pytest.fixture
def owner_procedure(owner_arcade):
    return Procedure.objects.create(
        arcade=owner_arcade,
        name="Owner Procedure",
        status=Procedure.Status.PENDING,
    )


@pytest.fixture
def other_procedure(other_arcade):
    return Procedure.objects.create(
        arcade=other_arcade,
        name="Other Procedure",
        status=Procedure.Status.PENDING,
    )


@pytest.fixture
def api_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def test_non_odonto_professional_cannot_access_odonto_routes(podology_professional):
    client = APIClient()
    client.force_authenticate(user=podology_professional)

    response = client.get("/odonto/arcades/")

    assert response.status_code == 403


def test_odonto_specialty_without_tenant_capability_cannot_access_odonto_routes(
    odonto_without_capability,
):
    client = APIClient()
    client.force_authenticate(user=odonto_without_capability)

    response = client.get("/odonto/arcades/")

    assert response.status_code == 403


def test_professional_lists_only_own_arcades(api_client, owner_arcade, other_arcade):
    response = api_client.get("/odonto/arcades/")

    assert response.status_code == 200, response.content
    ids = {item["id"] for item in response.json()}
    assert owner_arcade.id in ids
    assert other_arcade.id not in ids


def test_professional_cannot_read_other_professional_arcade(api_client, other_arcade):
    response = api_client.get(f"/odonto/arcades/{other_arcade.id}/")

    assert response.status_code == 404


def test_professional_cannot_create_arcade_for_other_professional_client(
    api_client,
    other_client,
):
    response = api_client.post(
        "/odonto/arcades/",
        {"client": other_client.id},
        format="json",
    )

    assert response.status_code == 400, response.content
    assert not DentalArcade.objects.filter(client=other_client).exists()


def test_arcade_create_ignores_payload_professional_and_uses_authenticated_user(
    api_client,
    owner,
    owner_client,
    other_professional,
):
    response = api_client.post(
        "/odonto/arcades/",
        {"client": owner_client.id, "professional": other_professional.id},
        format="json",
    )

    assert response.status_code == 201, response.content
    arcade = DentalArcade.objects.get(id=response.json()["id"])
    assert arcade.professional_id == owner.id
    assert arcade.professional_id != other_professional.id


def test_professional_lists_only_own_procedures(
    api_client,
    owner_procedure,
    other_procedure,
):
    response = api_client.get("/odonto/procedures/")

    assert response.status_code == 200, response.content
    ids = {item["id"] for item in response.json()}
    assert owner_procedure.id in ids
    assert other_procedure.id not in ids


def test_professional_cannot_create_procedure_for_other_arcade(
    api_client,
    other_arcade,
):
    response = api_client.post(
        "/odonto/procedures/",
        {"arcade": other_arcade.id, "name": "Cross Procedure"},
        format="json",
    )

    assert response.status_code == 400, response.content
    assert not Procedure.objects.filter(name="Cross Procedure").exists()


def test_professional_cannot_move_procedure_to_other_arcade(
    api_client,
    owner_procedure,
    other_arcade,
):
    response = api_client.patch(
        f"/odonto/procedures/{owner_procedure.id}/",
        {"arcade": other_arcade.id},
        format="json",
    )

    assert response.status_code == 400, response.content
    owner_procedure.refresh_from_db()
    assert owner_procedure.arcade_id != other_arcade.id


def test_professional_cannot_attach_surface_from_other_arcade(
    api_client,
    owner_arcade,
    other_arcade,
):
    other_tooth = Tooth.objects.create(
        arcade=other_arcade,
        sequence=1,
        international_number=11,
    )
    other_surface = Surface.objects.create(tooth=other_tooth, code=Surface.SurfaceCode.O)

    response = api_client.post(
        "/odonto/procedures/",
        {
            "arcade": owner_arcade.id,
            "surface": other_surface.id,
            "name": "Invalid Surface Procedure",
        },
        format="json",
    )

    assert response.status_code == 400, response.content
    assert not Procedure.objects.filter(name="Invalid Surface Procedure").exists()