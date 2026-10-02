from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import DeviceSession, Professional, Tenant, TenantMembership
from apps.bakery.models import BakeryCustomer

ADMIN_URL = "/api/v1/auth/bakery/login/admin/"
CUSTOMER_URL = "/api/v1/auth/bakery/login/customer/"
LEGACY_URL = "/api/v1/auth/bakery/login/"
PASSWORD = "senha-segura-123"


def make_tenant(slug="padaria-login-split", **extra):
    return Tenant.objects.create(
        name=f"Tenant {slug}",
        slug=slug,
        ecosystem=Tenant.Ecosystem.BAKERY,
        capabilities={"bakery": True},
        is_active=True,
        **extra,
    )


def make_user(email, tenant, role, alias=""):
    user = Professional.objects.create_user(email=email, password=PASSWORD, first_name="Nome")
    TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=role,
        is_active=True,
        login_alias=alias,
    )
    return user


def make_customer(user, tenant, status=BakeryCustomer.ApprovalStatus.APPROVED):
    return BakeryCustomer.objects.create(
        tenant=tenant,
        user=user,
        nickname="Cliente Teste",
        company_name="Cliente Teste Ltda",
        cnpj="12345678000199",
        phone="11999999999",
        zip_code="13480000",
        street="Rua Teste",
        number="10",
        neighborhood="Centro",
        city="Limeira",
        state="SP",
        status=status,
        credit_limit=Decimal("100.00"),
    )


def post(url, login, tenant_slug, password=PASSWORD):
    return APIClient().post(
        url,
        {"login": login, "password": password, "tenant_slug": tenant_slug},
        format="json",
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role", [TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN])
def test_admin_login_accepts_owner_and_admin(role):
    tenant = make_tenant()
    user = make_user("staff@bakery.test", tenant, role)

    response = post(ADMIN_URL, user.email, tenant.slug)

    assert response.status_code == 200, response.content
    assert response.data["role"] == role
    assert response.data["professional"]["email"] == user.email
    assert "customer" not in response.data
    token = AccessToken(response.data["access"])
    assert token["tenant_id"] == tenant.id
    assert token["ecosystem"] == "bakery"
    assert token["role"] == role


@pytest.mark.django_db
def test_admin_login_accepts_login_alias():
    tenant = make_tenant()
    make_user("dono@bakery.test", tenant, TenantMembership.Role.OWNER, alias="Dono")

    response = post(ADMIN_URL, "dono", tenant.slug)

    assert response.status_code == 200, response.content


@pytest.mark.django_db
def test_admin_login_rejects_member_without_issuing_tokens_or_session():
    tenant = make_tenant()
    user = make_user("cliente@bakery.test", tenant, TenantMembership.Role.MEMBER)
    make_customer(user, tenant)

    response = post(ADMIN_URL, user.email, tenant.slug)

    assert response.status_code == 400
    assert "login de cliente" in str(response.data)
    assert "access" not in response.data
    assert not DeviceSession.objects.filter(professional=user).exists()


@pytest.mark.django_db
def test_customer_login_accepts_approved_member():
    tenant = make_tenant()
    user = make_user("cliente@bakery.test", tenant, TenantMembership.Role.MEMBER, alias="cliente-teste")
    customer = make_customer(user, tenant)

    response = post(CUSTOMER_URL, "cliente-teste", tenant.slug)

    assert response.status_code == 200, response.content
    assert response.data["role"] == TenantMembership.Role.MEMBER
    assert response.data["customer"]["id"] == customer.id
    assert response.data["customer"]["status"] == BakeryCustomer.ApprovalStatus.APPROVED
    assert "professional" not in response.data
    token = AccessToken(response.data["access"])
    assert token["tenant_id"] == tenant.id
    assert token["ecosystem"] == "bakery"
    assert token["role"] == TenantMembership.Role.MEMBER
    assert token["device_id"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,message",
    [
        (BakeryCustomer.ApprovalStatus.PENDING, "não aprovado"),
        (BakeryCustomer.ApprovalStatus.BLOCKED, "bloqueada"),
    ],
)
def test_customer_login_rejects_pending_and_blocked(status, message):
    tenant = make_tenant()
    user = make_user("cliente@bakery.test", tenant, TenantMembership.Role.MEMBER)
    make_customer(user, tenant, status=status)

    response = post(CUSTOMER_URL, user.email, tenant.slug)

    assert response.status_code == 400
    assert message in str(response.data)
    assert "access" not in response.data
    assert not DeviceSession.objects.filter(professional=user).exists()


@pytest.mark.django_db
def test_customer_login_rejects_member_without_customer_record():
    tenant = make_tenant()
    user = make_user("semcliente@bakery.test", tenant, TenantMembership.Role.MEMBER)

    response = post(CUSTOMER_URL, user.email, tenant.slug)

    assert response.status_code == 400
    assert "access" not in response.data


@pytest.mark.django_db
@pytest.mark.parametrize("role", [TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN])
def test_customer_login_rejects_owner_and_admin_even_with_customer_record(role):
    tenant = make_tenant()
    user = make_user("staff@bakery.test", tenant, role)
    make_customer(user, tenant)

    response = post(CUSTOMER_URL, user.email, tenant.slug)

    assert response.status_code == 400
    assert "login administrativo" in str(response.data)
    assert "access" not in response.data


@pytest.mark.django_db
@pytest.mark.parametrize("url", [ADMIN_URL, CUSTOMER_URL])
def test_login_rejects_unknown_or_inactive_tenant(url):
    tenant = make_tenant()
    user = make_user("staff@bakery.test", tenant, TenantMembership.Role.OWNER)

    assert post(url, user.email, "tenant-inexistente").status_code == 400

    tenant.is_active = False
    tenant.save(update_fields=["is_active"])
    assert post(url, user.email, tenant.slug).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("url", [ADMIN_URL, CUSTOMER_URL])
def test_login_rejects_clinic_tenant(url):
    tenant = Tenant.objects.create(
        name="Clinica",
        slug="clinica-login-split",
        ecosystem=Tenant.Ecosystem.CLINIC,
        is_active=True,
    )
    user = make_user("staff@clinic.test", tenant, TenantMembership.Role.OWNER)

    assert post(url, user.email, tenant.slug).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("url", [ADMIN_URL, CUSTOMER_URL])
def test_login_rejects_membership_from_another_tenant(url):
    tenant_a = make_tenant("tenant-a")
    tenant_b = make_tenant("tenant-b")
    user = make_user("staff@bakery.test", tenant_a, TenantMembership.Role.OWNER)

    response = post(url, user.email, tenant_b.slug)

    assert response.status_code == 400
    assert "access" not in response.data


@pytest.mark.django_db
@pytest.mark.parametrize("url", [ADMIN_URL, CUSTOMER_URL])
def test_login_rejects_wrong_password_and_inactive_membership(url):
    tenant = make_tenant()
    user = make_user("staff@bakery.test", tenant, TenantMembership.Role.OWNER)

    assert post(url, user.email, tenant.slug, password="errada").status_code == 400

    TenantMembership.objects.filter(professional=user).update(is_active=False)
    assert post(url, user.email, tenant.slug).status_code == 400


@pytest.mark.django_db
def test_issued_tokens_keep_role_boundaries_on_bakery_endpoints():
    tenant = make_tenant()
    owner = make_user("owner@bakery.test", tenant, TenantMembership.Role.OWNER)
    member = make_user("cliente@bakery.test", tenant, TenantMembership.Role.MEMBER)
    customer = make_customer(member, tenant)

    admin_token = post(ADMIN_URL, owner.email, tenant.slug).data["access"]
    customer_token = post(CUSTOMER_URL, member.email, tenant.slug).data["access"]

    admin_client = APIClient()
    admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
    customer_client = APIClient()
    customer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token}")

    admin_customers = admin_client.get("/api/v1/bakery/customers/")
    own_customers = customer_client.get("/api/v1/bakery/customers/")
    assert admin_customers.status_code == 200
    assert own_customers.status_code == 200
    own_payload = own_customers.json()
    own_items = own_payload.get("results", own_payload) if isinstance(own_payload, dict) else own_payload
    assert [item["id"] for item in own_items] == [customer.id]

    assert admin_client.get("/api/v1/bakery/orders/").status_code == 200
    assert customer_client.get("/api/v1/bakery/orders/").status_code == 200
    assert admin_client.get("/api/v1/bakery/tenant/profile/").status_code in (200, 404)

    # Ações administrativas continuam proibidas ao token de cliente.
    forbidden = customer_client.post(
        f"/api/v1/bakery/customers/{customer.id}/block/", {}, format="json"
    )
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_legacy_single_login_endpoint_is_gone():
    tenant = make_tenant()
    user = make_user("staff@bakery.test", tenant, TenantMembership.Role.OWNER)

    assert post(LEGACY_URL, user.email, tenant.slug).status_code == 404
