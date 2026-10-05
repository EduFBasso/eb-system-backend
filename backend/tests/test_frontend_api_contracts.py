"""Contratos HTTP que os frontends Clinic e Bakery interpretam em runtime."""

import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import DeviceSession, Professional, Tenant, TenantMembership
from apps.bakery.models import BakeryCustomer, Order, Product

pytestmark = pytest.mark.django_db

PASSWORD = "senha-segura-123"
ADMIN_LOGIN_URL = "/api/v1/auth/bakery/login/admin/"
CUSTOMER_LOGIN_URL = "/api/v1/auth/bakery/login/customer/"

# Espelha frontend-bakery/src/services/authExpiry.ts
EXPIRED_TOKEN_DETAIL = re.compile(r"token not valid|token inválido|token expirado", re.I)
# Espelha frontend-clinic/src/utils/apiFetch.ts
DEVICE_SESSION_FRAGMENTS = (
    "sessão de dispositivo revogada",
    "sessão de dispositivo inativa",
    "sessão de dispositivo não encontrada",
)


def _login(url, login, tenant_slug):
    client = APIClient()
    response = client.post(
        url,
        {"login": login, "password": PASSWORD, "tenant_slug": tenant_slug},
        format="json",
    )
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client, response.data


@pytest.fixture
def bakery():
    tenant = Tenant.objects.create(
        name="Padaria Contratos",
        slug="padaria-contratos",
        ecosystem=Tenant.Ecosystem.BAKERY,
        capabilities={"bakery": True},
    )
    owner = Professional.objects.create_user(email="dono@contratos.test", password=PASSWORD)
    TenantMembership.objects.create(
        tenant=tenant, professional=owner, role=TenantMembership.Role.OWNER, is_active=True
    )
    member = Professional.objects.create_user(email="cliente@contratos.test", password=PASSWORD)
    TenantMembership.objects.create(
        tenant=tenant, professional=member, role=TenantMembership.Role.MEMBER, is_active=True
    )
    customer = BakeryCustomer.objects.create(
        tenant=tenant,
        user=member,
        nickname="Cliente Contrato",
        company_name="Cliente Contrato Ltda",
        cnpj="12345678000199",
        phone="11999999999",
        zip_code="13480000",
        street="Rua Teste",
        number="10",
        neighborhood="Centro",
        city="Limeira",
        state="SP",
        status=BakeryCustomer.ApprovalStatus.APPROVED,
        credit_limit=Decimal("100.00"),
    )
    product = Product.objects.create(tenant=tenant, name="Pao", price=Decimal("5.00"))
    admin_client, _ = _login(ADMIN_LOGIN_URL, owner.email, tenant.slug)
    customer_client, customer_login = _login(CUSTOMER_LOGIN_URL, member.email, tenant.slug)
    return {
        "tenant": tenant,
        "member": member,
        "customer": customer,
        "product": product,
        "admin": admin_client,
        "customer_client": customer_client,
        "customer_login": customer_login,
    }


def _create_order(bakery):
    response = bakery["customer_client"].post(
        "/api/v1/bakery/orders/",
        {
            "customer_id": bakery["customer"].pk,
            "delivery_date": (timezone.now() + timedelta(days=1)).isoformat(),
            "payment_method": Order.PaymentMethod.CASH,
            "items": [{"product_id": bakery["product"].pk, "quantity": 2}],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response


def test_bakery_customer_login_exposes_tenant_and_customer_fields(bakery):
    data = bakery["customer_login"]

    assert {"slug", "trade_name"} <= set(data["tenant"])
    assert {"id", "nickname", "customer_type", "status"} <= set(data["customer"])
    assert AccessToken(data["access"])["user_id"] == str(bakery["member"].pk)


def test_invalid_bearer_signals_token_not_valid_to_bakery_frontend(bakery):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer token-corrompido")

    response = client.get("/api/v1/bakery/orders/")

    assert response.status_code == 401
    assert response.json()["code"] == "token_not_valid"


def test_invalid_bearer_signals_token_not_valid_to_clinic_frontend():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer token-corrompido")

    response = client.get("/agenda/appointments/")

    assert response.status_code == 401
    assert response.json()["code"] == "token_not_valid"


def test_wrong_admin_password_is_not_reported_as_expired_token(bakery):
    order = _create_order(bakery)

    response = bakery["admin"].patch(
        f"/api/v1/bakery/orders/{order.data['id']}/status/",
        {"status": "CONFIRMED", "admin_password": "senha-errada"},
        format="json",
    )

    body = response.json()
    assert response.status_code == 401
    assert body.get("code") != "token_not_valid"
    assert not EXPIRED_TOKEN_DETAIL.search(body["detail"])


def test_revoked_device_session_message_matches_clinic_frontend_fragments(bakery):
    DeviceSession.objects.filter(professional=bakery["member"]).update(is_active=False)

    response = bakery["customer_client"].get("/sessions/summary")

    assert response.status_code == 401
    assert any(fragment in response.content.decode().lower() for fragment in DEVICE_SESSION_FRAGMENTS)


def test_customer_list_exposes_fields_used_to_bootstrap_customer_session(bakery):
    response = bakery["customer_client"].get("/api/v1/bakery/customers/")

    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["user"] == bakery["member"].pk
    assert {"id", "nickname", "status", "financial_limit", "financial_used", "financial_available"} <= set(row)


def test_order_create_response_exposes_fields_read_by_customer_frontend(bakery):
    response = _create_order(bakery)

    assert {"id", "order_number", "status", "delivery_date", "payment_method", "total_value"} <= set(
        response.json()
    )


def test_admin_order_list_exposes_pagination_and_fields_read_by_admin_frontend(bakery):
    _create_order(bakery)

    response = bakery["admin"].get(
        "/api/v1/bakery/orders/",
        {"open_only": "true", "ordering": "created_at", "page": 1, "page_size": 100},
    )

    body = response.json()
    assert response.status_code == 200
    assert {"count", "next", "previous", "results"} <= set(body)
    row = body["results"][0]
    assert {
        "id",
        "order_number",
        "customer_id",
        "customer_nickname",
        "status",
        "status_display",
        "created_at",
        "delivery_date",
        "payment_method",
        "total_value",
        "paid_at",
        "cancelled_at",
        "order_items",
        "shipping_street",
        "shipping_number",
        "shipping_neighborhood",
        "shipping_city",
        "shipping_state",
    } <= set(row)
    assert row["paid_at"] is None
    assert {"id", "product_name", "quantity", "unit_price", "subtotal"} <= set(row["order_items"][0])


def test_root_redirects_to_admin_and_health_accepts_both_forms(client):
    root = client.get("/")

    assert root.status_code == 302
    assert root["Location"] == "/admin/"
    assert client.get("/health").status_code == 200
    assert client.get("/health/").status_code == 200
