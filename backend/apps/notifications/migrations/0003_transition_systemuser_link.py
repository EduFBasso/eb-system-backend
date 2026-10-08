from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0003_transition_legacy_professional"),
        ("notifications", "0002_telegram_link_per_tenant"),
    ]

    operations = [
        migrations.AlterField(
            model_name="telegramprofessionallink",
            name="professional",
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name="telegram_links",
                to="authentication.systemuser",
                verbose_name="Profissional",
            ),
        ),
    ]
