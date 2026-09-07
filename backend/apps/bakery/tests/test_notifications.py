from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.bakery.models import BakeryCustomer, Order, Product
from apps.bakery.serializers.orders import OrderSerializer
from apps.bakery.services.notifications import notify_owner_order_cancelled
from apps.notifications.models import TelegramProfessionalLink


pytestmark = pytest.mark.django_db


def _make_tenant_with_owner(*, link_telegram: bool) -> tuple[Tenant, Professional]:
    tenant = Tenant.objects.create(
        name="Padaria Teste",
        slug=f"padaria-teste-{'linked' if link_telegram else 'unlinked'}",
        ecosystem=Tenant.Ecosystem.BAKERY,
        capabilities={"bakery": True},
    )
    owner = Professional.objects.create_user(
        email=f"owner-{'linked' if link_telegram else 'unlinked'}@bakery.test",
        first_name="Dono",
        last_name="Padaria",
    )
    TenantMembership.objects.create(
        tenant=tenant, professional=owner, role=TenantMembership.Role.OWNER, is_active=True
    )
    if link_telegram:
        TelegramProfessionalLink.objects.create(
            tenant=tenant, professional=owner, chat_id="12345", is_active=True
        )
    return tenant, owner


def _make_customer(tenant: Tenant) -> BakeryCustomer:
    user = Professional.objects.create_user(email=f"customer-{tenant.pk}@bakery.test")
    return BakeryCustomer.objects.create(
        tenant=tenant,
        user=user,
        nickname="Mercadinho da Esquina",
        phone="11999999999",
        zip_code="01310100",
        street="Av. Paulista",
        number="100",
        neighborhood="Bela Vista",
        city="São Paulo",
        state="SP",
        status=BakeryCustomer.ApprovalStatus.APPROVED,
    )


def _create_order(tenant: Tenant, customer: BakeryCustomer):
    product = Product.objects.create(tenant=tenant, name="Pao Frances", price=Decimal("0.75"))
    serializer = OrderSerializer(
        data={
            "customer_id": customer.pk,
            "delivery_date": (timezone.now() + timedelta(days=1)).isoformat(),
            "shipping_zip_code": "01310100",
            "shipping_street": "Av. Paulista",
            "shipping_number": "100",
            "shipping_neighborhood": "Bela Vista",
            "shipping_city": "São Paulo",
            "shipping_state": "SP",
            "payment_method": "CASH",
            "items": [{"product_id": product.pk, "quantity": 10}],
        },
        context={"tenant": tenant},
    )
    serializer.is_valid(raise_exception=True)
    return serializer.save(tenant=tenant)


def test_order_creation_notifies_linked_owner(django_capture_on_commit_callbacks):
    tenant, _owner = _make_tenant_with_owner(link_telegram=True)
    customer = _make_customer(tenant)

    mocked_response = Mock(status_code=200)
    mocked_response.json.return_value = {"ok": True, "result": {"message_id": 1}}

    with patch(
        "apps.notifications.services.telegram_client.requests.post",
        return_value=mocked_response,
    ) as mocked_post:
        with django_capture_on_commit_callbacks(execute=True):
            _create_order(tenant, customer)

    mocked_post.assert_called_once()
    assert mocked_post.call_args.kwargs["json"]["chat_id"] == "12345"
    assert "Mercadinho da Esquina" in mocked_post.call_args.kwargs["json"]["text"]


def test_order_creation_skips_owner_without_telegram_link(django_capture_on_commit_callbacks):
    tenant, _owner = _make_tenant_with_owner(link_telegram=False)
    customer = _make_customer(tenant)

    with patch("apps.notifications.services.telegram_client.requests.post") as mocked_post:
        with django_capture_on_commit_callbacks(execute=True):
            order = _create_order(tenant, customer)

    assert order.pk is not None
    mocked_post.assert_not_called()


def test_order_cancellation_notification_contains_order_details():
    tenant, _owner = _make_tenant_with_owner(link_telegram=True)
    customer = _make_customer(tenant)
    order = _create_order(tenant, customer)
    order.status = Order.Status.CANCELLED
    order.cancellation_reason = "Pedido duplicado"
    order.cancelled_at = timezone.now()
    order.save(update_fields=("status", "cancellation_reason", "cancelled_at", "updated_at"))
    mocked_response = Mock(status_code=200)
    mocked_response.json.return_value = {"ok": True, "result": {"message_id": 2}}

    with patch(
        "apps.notifications.services.telegram_client.requests.post",
        return_value=mocked_response,
    ) as mocked_post:
        notify_owner_order_cancelled(order, actor="Cliente Ciclo")

    text = mocked_post.call_args.kwargs["json"]["text"]
    assert f"Pedido: #{order.pk}" in text
    assert "10x Pao Frances" in text
    assert "Pedido duplicado" in text
    assert "Av. Paulista, 100" in text
    assert "Cancelado por: Cliente Ciclo" in text


def test_customer_registration_notifies_linked_owner(django_capture_on_commit_callbacks):
    from rest_framework.test import APIClient

    tenant, _owner = _make_tenant_with_owner(link_telegram=True)

    mocked_response = Mock(status_code=200)
    mocked_response.json.return_value = {"ok": True, "result": {"message_id": 1}}

    client = APIClient()
    with patch(
        "apps.notifications.services.telegram_client.requests.post",
        return_value=mocked_response,
    ) as mocked_post:
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                "/api/v1/bakery/customers/register/",
                {
                    "nickname": "Cliente Notificacao",
                    "customer_type": "PF",
                    "cpf": "11122233988",
                    "phone": "11999999977",
                    "zip_code": "01310100",
                    "street": "Avenida Paulista",
                    "number": "1000",
                    "neighborhood": "Bela Vista",
                    "city": "São Paulo",
                    "state": "SP",
                    "tenant_slug": tenant.slug,
                },
                format="json",
            )

    assert response.status_code == 201
    mocked_post.assert_called_once()
    assert mocked_post.call_args.kwargs["json"]["chat_id"] == "12345"
    assert "Cliente Notificacao" in mocked_post.call_args.kwargs["json"]["text"]
