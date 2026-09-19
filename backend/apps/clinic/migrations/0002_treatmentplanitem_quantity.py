from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinic', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='treatmentplanitem',
            name='quantity',
            field=models.DecimalField(
                decimal_places=2,
                default=1,
                max_digits=10,
                verbose_name='Quantidade',
            ),
        ),
    ]
