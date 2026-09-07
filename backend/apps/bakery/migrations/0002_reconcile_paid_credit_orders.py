from django.db import migrations
from django.utils import timezone


def reconcile_paid_credit_orders(apps, schema_editor):
    Order = apps.get_model("bakery", "Order")
    CreditLedgerEntry = apps.get_model("bakery", "CreditLedgerEntry")

    paid_orders = Order.objects.filter(
        status__in=("CONFIRMED", "DELIVERED"),
        payment_method="CREDIT",
    ).iterator()

    for order in paid_orders:
        reference_key = f"order:{order.pk}:payment-credit"
        CreditLedgerEntry.objects.get_or_create(
            tenant_id=order.tenant_id,
            reference_key=reference_key,
            defaults={
                "customer_id": order.customer_id,
                "order_id": order.pk,
                "entry_type": "CREDIT",
                "amount": order.total_value,
                "description": f"Payment received for order #{order.pk}",
            },
        )
        if order.paid_at is None:
            Order.objects.filter(pk=order.pk).update(paid_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("bakery", "0001_initial")]

    operations = [
        migrations.RunPython(reconcile_paid_credit_orders, migrations.RunPython.noop),
    ]
