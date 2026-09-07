from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.bakery.models import BakeryCustomer, CreditLedgerEntry, Order, OrderItem, Product


pytestmark = pytest.mark.django_db


def make_tenant() -> Tenant:
    return Tenant.objects.create(
        name="Padaria Ciclo de Pedido",
        slug="padaria-ciclo-pedido",
        ecosystem=Tenant.Ecosystem.BAKERY,
        capabilities={"bakery": True},
    )


def make_customer(tenant: Tenant) -> tuple[Professional, BakeryCustomer]:
    user = Professional.objects.create_user(email="cliente-ciclo@bakery.test", password="client-pass")
    TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=TenantMembership.Role.MEMBER,
        is_active=True,
    )
    customer = BakeryCustomer.objects.create(
        tenant=tenant,
        user=user,
        nickname="Cliente Ciclo",
        company_name="Cliente Ciclo Ltda",
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
    return user, customer


def make_order(tenant: Tenant, customer: BakeryCustomer, *, payment_method: str) -> Order:
    product = Product.objects.create(tenant=tenant, name="Pao de Teste", price=Decimal("5.00"))
    order = Order.objects.create(
        tenant=tenant,
        customer=customer,
        delivery_date=timezone.now() + timedelta(days=1),
        shipping_zip_code=customer.zip_code,
        shipping_street=customer.street,
        shipping_number=customer.number,
        shipping_neighborhood=customer.neighborhood,
        shipping_city=customer.city,
        shipping_state=customer.state,
        payment_method=payment_method,
    )
    OrderItem.objects.create(
        tenant=tenant,
        order=order,
        product=product,
        quantity=2,
    )
    order.refresh_from_db()
    if payment_method == Order.PaymentMethod.CREDIT:
        CreditLedgerEntry.objects.create(
            tenant=tenant,
            customer=customer,
            order=order,
            entry_type=CreditLedgerEntry.EntryType.DEBIT,
            amount=order.total_value,
            description=f"Credit reservation for order #{order.pk}",
            reference_key=f"order:{order.pk}:debit",
        )
    return order


def test_customer_cancel_is_idempotent_and_reverses_credit_once(
    django_capture_on_commit_callbacks,
):
    tenant = make_tenant()
    user, customer = make_customer(tenant)
    order = make_order(tenant, customer, payment_method=Order.PaymentMethod.CREDIT)
    client = APIClient()
    client.force_authenticate(user=user)

    with patch("apps.bakery.views.orders.notify_owner_order_cancelled") as notify:
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                f"/api/v1/bakery/orders/{order.pk}/cancel/",
                {
                    "reason": "Pedido feito em duplicidade",
                    "customer_password": "client-pass",
                },
                format="json",
            )

    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert order.cancellation_reason == "Pedido feito em duplicidade"
    assert order.cancelled_at is not None
    assert order.items.count() == 1
    assert CreditLedgerEntry.objects.filter(
        order=order,
        entry_type=CreditLedgerEntry.EntryType.CREDIT,
        reference_key=f"order:{order.pk}:cancel-credit",
    ).count() == 1
    notify.assert_called_once()

    second_response = client.post(
        f"/api/v1/bakery/orders/{order.pk}/cancel/",
        {
            "reason": "Pedido feito em duplicidade",
            "customer_password": "client-pass",
        },
        format="json",
    )
    assert second_response.status_code == 200
    assert CreditLedgerEntry.objects.filter(
        order=order,
        entry_type=CreditLedgerEntry.EntryType.CREDIT,
    ).count() == 1


def test_customer_cancel_requires_customer_password():
    tenant = make_tenant()
    user, customer = make_customer(tenant)
    order = make_order(tenant, customer, payment_method=Order.PaymentMethod.CASH)
    client = APIClient()
    client.force_authenticate(user=user)

    missing = client.post(
        f"/api/v1/bakery/orders/{order.pk}/cancel/",
        {"reason": "Pedido feito em duplicidade"},
        format="json",
    )
    incorrect = client.post(
        f"/api/v1/bakery/orders/{order.pk}/cancel/",
        {"reason": "Pedido feito em duplicidade", "customer_password": "errada"},
        format="json",
    )

    assert missing.status_code == 400
    assert missing.json()["detail"] == "customer_password é obrigatória."
    assert incorrect.status_code == 401
    assert incorrect.json()["detail"] == "Senha do cliente incorreta."
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING


def test_bakery_login_embeds_tenant_context_in_jwt(client):
    tenant = make_tenant()
    user, _customer = make_customer(tenant)

    response = client.post(
        "/api/v1/auth/bakery/login/",
        {
            "login": user.email,
            "password": "client-pass",
            "tenant_slug": tenant.slug,
        },
    )

    assert response.status_code == 200
    token = AccessToken(response.json()["access"])
    assert token["tenant_id"] == tenant.id
    assert token["ecosystem"] == "bakery"
    assert token["role"] == TenantMembership.Role.MEMBER


def test_order_generic_mutations_are_blocked():
    tenant = make_tenant()
    user, customer = make_customer(tenant)
    order = make_order(tenant, customer, payment_method=Order.PaymentMethod.CASH)
    client = APIClient()
    client.force_authenticate(user=user)

    patch_response = client.patch(
        f"/api/v1/bakery/orders/{order.pk}/",
        {"notes": "Alterado"},
        format="json",
    )
    delete_response = client.delete(f"/api/v1/bakery/orders/{order.pk}/")

    assert patch_response.status_code == 405
    assert delete_response.status_code == 405
    assert Order.objects.filter(pk=order.pk).exists()


def test_customer_can_update_profile_but_not_governance_fields():
    tenant = make_tenant()
    user, customer = make_customer(tenant)
    other_user = Professional.objects.create_user(
        email="outro-cliente@bakery.test",
        password="client-pass",
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        f"/api/v1/bakery/customers/{customer.pk}/",
        {
            "nickname": "Novo Apelido",
            "phone": "11988887777",
            "status": BakeryCustomer.ApprovalStatus.BLOCKED,
            "credit_limit": "9999.00",
            "user": other_user.pk,
        },
        format="json",
    )

    assert response.status_code == 200
    customer.refresh_from_db()
    assert customer.nickname == "Novo Apelido"
    assert customer.phone == "11988887777"
    assert customer.status == BakeryCustomer.ApprovalStatus.APPROVED
    assert customer.credit_limit == Decimal("100.00")
    assert customer.user == user


def test_admin_status_transition_requires_password():
    tenant = make_tenant()
    _customer_user, customer = make_customer(tenant)
    order = make_order(tenant, customer, payment_method=Order.PaymentMethod.CREDIT)
    admin = Professional.objects.create_user(
        email="admin-ciclo@bakery.test",
        password="admin-pass",
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=admin,
        role=TenantMembership.Role.ADMIN,
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    denied = client.patch(
        f"/api/v1/bakery/orders/{order.pk}/status/",
        {"status": Order.Status.CONFIRMED, "admin_password": "wrong"},
        format="json",
    )
    accepted = client.patch(
        f"/api/v1/bakery/orders/{order.pk}/status/",
        {"status": Order.Status.CONFIRMED, "admin_password": "admin-pass"},
        format="json",
    )

    assert denied.status_code == 401
    assert accepted.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.CONFIRMED
    assert order.paid_at is not None
    assert CreditLedgerEntry.objects.filter(
        order=order,
        entry_type=CreditLedgerEntry.EntryType.CREDIT,
        reference_key=f"order:{order.pk}:payment-credit",
    ).count() == 1
    customer.refresh_from_db()
    assert customer.financial_used == Decimal("0.00")
    assert customer.financial_available == Decimal("100.00")

    repeated = client.patch(
        f"/api/v1/bakery/orders/{order.pk}/status/",
        {"status": Order.Status.CONFIRMED, "admin_password": "admin-pass"},
        format="json",
    )
    assert repeated.status_code == 200
    assert CreditLedgerEntry.objects.filter(
        order=order,
        entry_type=CreditLedgerEntry.EntryType.CREDIT,
        reference_key=f"order:{order.pk}:payment-credit",
    ).count() == 1
