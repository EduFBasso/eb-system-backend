import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="telegramprofessionallink",
            name="professional",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="telegram_links",
                to="authentication.professional",
                verbose_name="Profissional",
            ),
        ),
        migrations.AddConstraint(
            model_name="telegramprofessionallink",
            constraint=models.UniqueConstraint(
                fields=("professional", "tenant"),
                name="uniq_telegram_link_professional_tenant",
            ),
        ),
    ]
