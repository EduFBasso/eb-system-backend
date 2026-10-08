"""Matriz de isolamento por tenant e ecossistema (Execução 6)."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.authentication.models import SystemUser, Tenant, TenantMembership
from apps.bakery.models import BakeryCustomer, CreditLedgerEntry, Order, Product as BakeryProduct
from apps.clinic.models.clients import Client
from apps.clinic.models.inventory import Service
from apps.clinic.models.treatment import TreatmentPlan

pytestmark = pytest.mark.django_db

PASSWORD = "senha-segura-123"
BAKERY_ADMIN_LOGIN = "/api/v1/auth/bakery/login/admin/"
BAKERY_CUSTOMER_LOGIN = "/api/v1/auth/bakery/login/customer/"
CLINIC_LOGIN = "/token/"

BAKERY_ROUTES = [
    "/api/v1/bakery/customers/",
    "/api/v1/bakery/products/",
    "/api/v1/bakery/orders/",
    "/api/v1/bakery/ledger-entries/",
    "/api/v1/bakery/tenant/profile/",
]
CLINIC_ROUTES = [
    "/register/clients/",
    "/register/clients-basic/",
    "/inventory/services/",
    "/inventory/products/",
    "/clinic/treatment/plans/",
    "/agenda/appointments/",
    # Novo prefixo canônico (dual-mount) — mesma matriz de isolamento.
    "/api/v1/clinic/register/clients/",
    "/api/v1/clinic/register/clients-basic/",
    "/api/v1/clinic/inventory/services/",
    "/api/v1/clinic/inventory/products/",
    "/api/v1/clinic/treatment/plans/",
    "/api/v1/clinic/agenda/appointments/",
]


def _login(url, login, slug):
    client = APIClient()
    response = client.post(
        url, {"login": login, "password": PASSWORD, "tenant_slug": slug}, format="json"
    )
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


def _rows(response):
    payload = response.json()
    return payload.get("results", []) if isinstance(payload, dict) else payload


def _user(email):
    return SystemUser.objects.create_user(email=email, password=PASSWORD)


def _member(tenant, user, role):
    return TenantMembership.objects.create(
        tenant=tenant, professional=user, role=role, is_active=True
    )


def _bakery_tenant(slug):
    return Tenant.objects.create(
        name=slug, slug=slug, ecosystem=Tenant.Ecosystem.BAKERY, capabilities={"bakery": True}
    )


def _clinic_tenant(slug):
    return Tenant.objects.create(
        name=slug,
        slug=slug,
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={"clinic": True, "podologia": True},
    )


def _bakery_customer(tenant, user, nickname, document):
    return BakeryCustomer.objects.create(
        tenant=tenant,
        user=user,
        nickname=nickname,
        company_name=f"{nickname} Ltda",
        cnpj=document,
        phone=f"119{document[-8:]}",
        zip_code="13480000",
        street="Rua Teste",
        number="10",
        neighborhood="Centro",
        city="Limeira",
        state="SP",
        status=BakeryCustomer.ApprovalStatus.APPROVED,
        credit_limit=Decimal("100.00"),
    )


def _order(client, customer, product, payment_method=Order.PaymentMethod.CREDIT):
    response = client.post(
        "/api/v1/bakery/orders/",
        {
            "customer_id": customer.pk,
            "delivery_date": (timezone.now() + timedelta(days=1)).isoformat(),
            "payment_method": payment_method,
            "items": [{"product_id": product.pk, "quantity": 2}],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return Order.objects.get(pk=response.data["id"])


@pytest.fixture
def world():
    bakery_a, bakery_b = _bakery_tenant("padaria-a"), _bakery_tenant("padaria-b")
    clinic_c, clinic_d = _clinic_tenant("clinica-c"), _clinic_tenant("clinica-d")

    # Mesmo usuário com acesso a Bakery A e Clinic C: o token escolhe o ecossistema.
    dual = _user("dual@isolamento.test")
    _member(bakery_a, dual, TenantMembership.Role.OWNER)
    clinic_membership = _member(clinic_c, dual, TenantMembership.Role.OWNER)

    owner_b = _user("dono-b@isolamento.test")
    _member(bakery_b, owner_b, TenantMembership.Role.OWNER)
    member_a, member_b = _user("cliente-a@isolamento.test"), _user("cliente-b@isolamento.test")
    _member(bakery_a, member_a, TenantMembership.Role.MEMBER)
    _member(bakery_b, member_b, TenantMembership.Role.MEMBER)

    customer_a = _bakery_customer(bakery_a, member_a, "Cliente A", "11111111000101")
    customer_b = _bakery_customer(bakery_b, member_b, "Cliente B", "22222222000102")
    product_a = BakeryProduct.objects.create(tenant=bakery_a, name="Pao A", price=Decimal("5.00"))
    product_b = BakeryProduct.objects.create(tenant=bakery_b, name="Pao B", price=Decimal("5.00"))

    customer_b_client = _login(BAKERY_CUSTOMER_LOGIN, member_b.email, bakery_b.slug)
    order_b = _order(customer_b_client, customer_b, product_b)

    client_c = Client.objects.create(
        tenant=clinic_c, first_name="Ana", last_name="C", phone="11970000001"
    )
    client_d = Client.objects.create(
        tenant=clinic_d, first_name="Davi", last_name="D", phone="11970000002"
    )
    service_d = Service.objects.create(tenant=clinic_d, name="Servico D")

    return SimpleNamespace(
        bakery_a=bakery_a,
        bakery_b=bakery_b,
        clinic_c=clinic_c,
        clinic_d=clinic_d,
        dual=dual,
        clinic_membership=clinic_membership,
        member_a=member_a,
        customer_a=customer_a,
        customer_b=customer_b,
        product_a=product_a,
        product_b=product_b,
        order_b=order_b,
        client_c=client_c,
        client_d=client_d,
        service_d=service_d,
        dual_bakery=_login(BAKERY_ADMIN_LOGIN, dual.email, bakery_a.slug),
        dual_clinic=_login(CLINIC_LOGIN, dual.email, clinic_c.slug),
        customer_a_client=_login(BAKERY_CUSTOMER_LOGIN, member_a.email, bakery_a.slug),
    )


@pytest.mark.parametrize("path", BAKERY_ROUTES)
def test_clinic_token_is_denied_on_bakery_routes(world, path):
    assert world.dual_clinic.get(path).status_code == 403


@pytest.mark.parametrize("path", CLINIC_ROUTES)
def test_bakery_token_never_receives_clinic_data(world, path):
    response = world.dual_bakery.get(path)

    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert _rows(response) == []


def test_bakery_token_cannot_write_clinic_data(world):
    before = Client.objects.count()

    response = world.dual_bakery.post(
        "/register/clients/",
        {"first_name": "Intruso", "last_name": "Bakery", "phone": "11970000999"},
        format="json",
    )

    assert response.status_code in (400, 403)
    assert Client.objects.count() == before


def test_bakery_admin_cannot_reach_other_tenant_resources(world):
    b_customer, b_order = world.customer_b.pk, world.order_b.pk
    admin_body = {"admin_password": PASSWORD, "reason": "isolamento"}
    attempts = [
        ("get", f"/api/v1/bakery/customers/{b_customer}/", None),
        ("get", f"/api/v1/bakery/orders/{b_order}/", None),
        ("post", f"/api/v1/bakery/customers/{b_customer}/block/", admin_body),
        ("post", f"/api/v1/bakery/customers/{b_customer}/reveal-password/", admin_body),
        ("patch", f"/api/v1/bakery/orders/{b_order}/status/", {**admin_body, "status": "CONFIRMED"}),
        ("post", f"/api/v1/bakery/orders/{b_order}/cancel/", admin_body),
    ]

    for method, path, body in attempts:
        response = getattr(world.dual_bakery, method)(path, body, format="json")
        assert response.status_code == 404, (method, path, response.content)

    world.customer_b.refresh_from_db()
    world.order_b.refresh_from_db()
    assert world.customer_b.status == BakeryCustomer.ApprovalStatus.APPROVED
    assert world.order_b.status == Order.Status.PENDING
    assert world.order_b.cancelled_at is None


def test_bakery_lists_exclude_other_tenant_rows(world):
    ledger_b = CreditLedgerEntry.objects.filter(order=world.order_b)
    assert ledger_b.exists()
    foreign = {
        "customers": {world.customer_b.pk},
        "products": {world.product_b.pk},
        "orders": {world.order_b.pk},
        "ledger-entries": set(ledger_b.values_list("pk", flat=True)),
    }

    for resource, foreign_ids in foreign.items():
        response = world.dual_bakery.get(f"/api/v1/bakery/{resource}/")
        assert response.status_code == 200, (resource, response.content)
        assert foreign_ids.isdisjoint({row["id"] for row in _rows(response)}), resource


def test_bakery_customer_cannot_order_for_customer_of_other_tenant(world):
    before = Order.objects.count()

    response = world.customer_a_client.post(
        "/api/v1/bakery/orders/",
        {
            "customer_id": world.customer_b.pk,
            "delivery_date": (timezone.now() + timedelta(days=1)).isoformat(),
            "payment_method": Order.PaymentMethod.CASH,
            "items": [{"product_id": world.product_a.pk, "quantity": 1}],
        },
        format="json",
    )

    assert response.status_code in (400, 403)
    assert Order.objects.count() == before


def test_bakery_write_uses_token_tenant_not_payload_tenant(world):
    response = world.dual_bakery.post(
        "/api/v1/bakery/products/",
        {"name": "Pao Forjado", "price": "7.00", "tenant": world.bakery_b.pk},
        format="json",
    )

    assert response.status_code == 201, response.content
    created = BakeryProduct.objects.get(pk=response.data["id"])
    assert created.tenant_id == world.bakery_a.pk


@pytest.mark.parametrize("deactivate", ["membership", "tenant"])
def test_issued_bakery_token_stops_working_when_access_is_revoked(world, deactivate):
    assert world.dual_bakery.get("/api/v1/bakery/orders/").status_code == 200

    if deactivate == "membership":
        TenantMembership.objects.filter(tenant=world.bakery_a, professional=world.dual).update(
            is_active=False
        )
    else:
        Tenant.objects.filter(pk=world.bakery_a.pk).update(is_active=False)

    assert world.dual_bakery.get("/api/v1/bakery/orders/").status_code == 403


def test_clinic_inventory_and_clients_are_scoped_to_token_tenant(world):
    client_c = world.dual_clinic

    clients = {row["id"] for row in _rows(client_c.get("/register/clients/"))}
    services = {row["id"] for row in _rows(client_c.get("/inventory/services/"))}
    assert world.client_c.pk in clients and world.client_d.pk not in clients
    assert world.service_d.pk not in services
    assert client_c.get(f"/inventory/services/{world.service_d.pk}/").status_code == 404
    assert (
        client_c.patch(
            f"/inventory/services/{world.service_d.pk}/", {"name": "Hack"}, format="json"
        ).status_code
        == 404
    )
    assert client_c.delete(f"/inventory/services/{world.service_d.pk}/").status_code == 404
    world.service_d.refresh_from_db()
    assert world.service_d.name == "Servico D"


def test_clinic_canonical_prefix_is_scoped_like_legacy_root(world):
    """O novo prefixo /api/v1/clinic/ deve respeitar o mesmo escopo do legado."""
    client_c = world.dual_clinic

    clients = {row["id"] for row in _rows(client_c.get("/api/v1/clinic/register/clients/"))}
    assert world.client_c.pk in clients and world.client_d.pk not in clients

    # Escrita pelo novo prefixo usa o tenant do token, nunca o do payload.
    response = client_c.post(
        "/api/v1/clinic/inventory/services/",
        {"name": "Servico Canonico", "tenant": world.clinic_d.pk},
        format="json",
    )
    assert response.status_code == 201, response.content
    assert Service.objects.get(pk=response.data["id"]).tenant_id == world.clinic_c.pk


def test_clinic_write_uses_token_tenant_not_payload_tenant(world):
    response = world.dual_clinic.post(
        "/inventory/services/",
        {"name": "Servico Forjado", "tenant": world.clinic_d.pk},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert Service.objects.get(pk=response.data["id"]).tenant_id == world.clinic_c.pk


def test_clinic_plan_cannot_use_client_from_other_tenant(world):
    response = world.dual_clinic.post(
        "/clinic/treatment/plans/",
        {"client": world.client_d.pk, "name": "Plano cruzado"},
        format="json",
    )

    assert response.status_code in (400, 403)
    assert not TreatmentPlan.objects.filter(client=world.client_d).exists()


@pytest.mark.parametrize("deactivate", ["membership", "tenant"])
@pytest.mark.parametrize("path", CLINIC_ROUTES)
def test_issued_clinic_token_stops_exposing_data_when_access_is_revoked(world, path, deactivate):
    if deactivate == "membership":
        world.clinic_membership.is_active = False
        world.clinic_membership.save(update_fields=["is_active"])
    else:
        Tenant.objects.filter(pk=world.clinic_c.pk).update(is_active=False)

    response = world.dual_clinic.get(path)

    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert _rows(response) == []
