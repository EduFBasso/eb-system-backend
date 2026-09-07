"""Owner-facing Telegram notifications for the bakery ecosystem.

Uses the shared apps.notifications engine; does not know about clinic at all.
"""
import logging

from apps.authentication.models import TenantMembership
from apps.bakery.models import BakeryCustomer, Order
from apps.notifications.models import TelegramProfessionalLink
from apps.notifications.services.telegram_client import (
    TelegramDeliveryError,
    send_via_link,
)

logger = logging.getLogger(__name__)


def build_new_order_text(order: Order) -> str:
    lines = [
        "Novo pedido recebido",
        "",
        f"Pedido: #{order.pk}",
        f"Cliente: {order.customer.nickname}",
        f"Telefone: {order.customer.phone or 'Não informado'}",
        "Itens:",
        *[
            f"- {item.quantity}x {item.product.name} — R$ {item.subtotal}"
            for item in order.items.select_related("product").all()
        ],
        f"Total: R$ {order.total_value}",
        f"Pagamento: {order.get_payment_method_display()}",
    ]
    if order.delivery_date:
        lines.append(f"Entrega: {order.delivery_date.strftime('%d/%m/%Y')}")
    lines.append(
        "Endereço: "
        f"{order.shipping_street}, {order.shipping_number}, "
        f"{order.shipping_neighborhood}, {order.shipping_city}/{order.shipping_state}, "
        f"CEP {order.shipping_zip_code}"
    )
    return "\n".join(lines)


def notify_owner_new_order(order: Order) -> None:
    """Best-effort notification: never raises, never blocks order creation."""
    owner_ids = TenantMembership.objects.filter(
        tenant_id=order.tenant_id,
        role__in=[TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN],
        is_active=True,
    ).values_list("professional_id", flat=True)

    links = TelegramProfessionalLink.objects.filter(
        tenant_id=order.tenant_id,
        professional_id__in=list(owner_ids),
        is_active=True,
    )

    text = build_new_order_text(order)
    for link in links:
        try:
            send_via_link(link, text=text)
        except TelegramDeliveryError as exc:
            logger.warning(
                "Falha ao notificar dono (professional_id=%s) sobre pedido #%s: %s",
                link.professional_id,
                order.pk,
                exc,
            )


def build_cancelled_order_text(order: Order, *, actor: str) -> str:
    lines = [
        "Pedido cancelado",
        "",
        f"Pedido: #{order.pk}",
        f"Cliente: {order.customer.nickname}",
        f"Telefone: {order.customer.phone or 'Não informado'}",
        "Itens:",
        *[
            f"- {item.quantity}x {item.product.name} — R$ {item.subtotal}"
            for item in order.items.select_related("product").all()
        ],
        f"Total: R$ {order.total_value}",
        f"Pagamento: {order.get_payment_method_display()}",
        f"Entrega: {order.delivery_date.strftime('%d/%m/%Y')}",
        "Endereço: "
        f"{order.shipping_street}, {order.shipping_number}, "
        f"{order.shipping_neighborhood}, {order.shipping_city}/{order.shipping_state}, "
        f"CEP {order.shipping_zip_code}",
        f"Motivo: {order.cancellation_reason}",
        f"Cancelado por: {actor}",
        f"Horário: {order.cancelled_at.strftime('%d/%m/%Y %H:%M')}",
    ]
    return "\n".join(lines)


def notify_owner_order_cancelled(order: Order, *, actor: str) -> None:
    """Best-effort notification: never raises, never blocks cancellation."""
    owner_ids = TenantMembership.objects.filter(
        tenant_id=order.tenant_id,
        role__in=[TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN],
        is_active=True,
    ).values_list("professional_id", flat=True)
    links = TelegramProfessionalLink.objects.filter(
        tenant_id=order.tenant_id,
        professional_id__in=list(owner_ids),
        is_active=True,
    )
    text = build_cancelled_order_text(order, actor=actor)
    for link in links:
        try:
            send_via_link(link, text=text)
        except TelegramDeliveryError as exc:
            logger.warning(
                "Falha ao notificar dono (professional_id=%s) sobre cancelamento #%s: %s",
                link.professional_id,
                order.pk,
                exc,
            )


def build_new_customer_text(customer: BakeryCustomer) -> str:
    lines = [
        "🥖 Novo cliente cadastrado no sistema!",
        "",
        f"Apelido: {customer.nickname}",
        f"Tipo: {customer.customer_type}",
        f"Telefone: {customer.phone or 'Não informado'}",
        f"Status: {customer.status}",
        "",
        "Acesse o painel administrativo para aprovar o cadastro e definir o limite de crédito.",
    ]
    return "\n".join(lines)


def notify_owner_new_customer(customer: BakeryCustomer) -> None:
    """Best-effort notification: never raises, never blocks customer registration."""
    owner_ids = TenantMembership.objects.filter(
        tenant_id=customer.tenant_id,
        role__in=[TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN],
        is_active=True,
    ).values_list("professional_id", flat=True)

    links = TelegramProfessionalLink.objects.filter(
        tenant_id=customer.tenant_id,
        professional_id__in=list(owner_ids),
        is_active=True,
    )

    text = build_new_customer_text(customer)
    for link in links:
        try:
            send_via_link(link, text=text)
        except TelegramDeliveryError as exc:
            logger.warning(
                "Falha ao notificar dono (professional_id=%s) sobre novo cliente #%s: %s",
                link.professional_id,
                customer.pk,
                exc,
            )
