"""Owner-facing Telegram notifications for the bakery ecosystem.

Uses the shared apps.notifications engine; does not know about clinic at all.
"""
import logging

from apps.authentication.models import TenantMembership
from apps.bakery.models import Order
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
        f"Cliente: {order.customer.nickname}",
        f"Total: R$ {order.total_value}",
    ]
    if order.delivery_date:
        lines.append(f"Entrega: {order.delivery_date.strftime('%d/%m/%Y')}")
    return "\n".join(lines)


def notify_owner_new_order(order: Order) -> None:
    """Best-effort notification: never raises, never blocks order creation."""
    owner_ids = TenantMembership.objects.filter(
        tenant_id=order.tenant_id,
        role=TenantMembership.Role.OWNER,
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
