from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bakery", "0003_bakerycustomer_uq_bakery_customer_tenant_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="original_address_text",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_address_text",
            field=models.TextField(blank=True),
        ),
    ]