import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import Professional, Tenant, TenantMembership


pytestmark = pytest.mark.django_db


def make_tenant(slug: str) -> Tenant:
    return Tenant.objects.create(
        name=slug.replace("-", " ").title(),
        trade_name="Nome inicial",
        slug=slug,
        ecosystem=Tenant.Ecosystem.BAKERY,
        capabilities={"bakery": True},
    )


def authenticated_client(user: Professional, tenant: Tenant) -> APIClient:
    token = AccessToken.for_user(user)
    token["tenant_id"] = tenant.id
    token["ecosystem"] = "bakery"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def make_member(tenant: Tenant, email: str, role: str) -> Professional:
    user = Professional.objects.create_user(email=email, password="test-password")
    TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=role,
        is_active=True,
    )
    return user


def test_owner_can_update_only_editable_tenant_profile_fields():
    tenant = make_tenant("padaria-perfil-a")
    owner = make_member(tenant, "owner-a@example.test", TenantMembership.Role.OWNER)
    client = authenticated_client(owner, tenant)

    response = client.patch(
        "/api/v1/bakery/tenant/profile/",
        {
            "trade_name": "Padaria Central",
            "zip_code": "13000-000",
            "street": "Rua Central",
            "number": "100",
            "city": "Campinas",
            "state": "sp",
            "slug": "tenant-nao-pode-mudar",
            "ecosystem": "clinic",
        },
        format="json",
    )

    assert response.status_code == 200
    tenant.refresh_from_db()
    assert tenant.trade_name == "Padaria Central"
    assert tenant.state == "SP"
    assert tenant.slug == "padaria-perfil-a"
    assert tenant.ecosystem == Tenant.Ecosystem.BAKERY


def test_member_cannot_update_tenant_profile():
    tenant = make_tenant("padaria-perfil-member")
    member = make_member(tenant, "member@example.test", TenantMembership.Role.MEMBER)
    client = authenticated_client(member, tenant)

    response = client.patch(
        "/api/v1/bakery/tenant/profile/",
        {"trade_name": "Tentativa indevida"},
        format="json",
    )

    assert response.status_code == 403
    tenant.refresh_from_db()
    assert tenant.trade_name == "Nome inicial"


def test_tenant_profile_is_scoped_to_tenant_from_token():
    tenant_a = make_tenant("padaria-perfil-a-isolada")
    tenant_b = make_tenant("padaria-perfil-b-isolada")
    owner_b = make_member(tenant_b, "owner-b@example.test", TenantMembership.Role.OWNER)
    client = authenticated_client(owner_b, tenant_b)

    response = client.get("/api/v1/bakery/tenant/profile/")

    assert response.status_code == 200
    assert response.json()["slug"] == tenant_b.slug
    assert response.json()["slug"] != tenant_a.slug


def test_non_bakery_membership_cannot_use_bakery_tenant_profile():
    tenant = Tenant.objects.create(
        name="Clinica Perfil",
        trade_name="Clinica Perfil",
        slug="clinica-perfil",
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={"clinic": True},
    )
    owner = make_member(tenant, "clinic-owner@example.test", TenantMembership.Role.OWNER)
    client = authenticated_client(owner, tenant)

    response = client.get("/api/v1/bakery/tenant/profile/")

    assert response.status_code == 403