from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0007_alter_tenant_trade_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="zip_code",
            field=models.CharField(blank=True, default="", max_length=9, verbose_name="CEP"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="street",
            field=models.CharField(blank=True, default="", max_length=160, verbose_name="Rua / Avenida"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="number",
            field=models.CharField(blank=True, default="", max_length=20, verbose_name="Número"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="neighborhood",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="Bairro"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="city",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="Cidade"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="state",
            field=models.CharField(blank=True, default="", max_length=2, verbose_name="Estado"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="complement",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="Complemento"),
        ),
    ]