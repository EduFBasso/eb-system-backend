from django.db import migrations, models
from django.db.models.functions import Lower, Trim


class Migration(migrations.Migration):

    dependencies = [
        ("bakery", "0004_order_address_snapshots"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="bakerycustomer",
            constraint=models.UniqueConstraint(
                Lower(Trim("nickname")),
                "tenant",
                name="uq_bakery_customer_tenant_nickname_ci",
            ),
        ),
    ]
