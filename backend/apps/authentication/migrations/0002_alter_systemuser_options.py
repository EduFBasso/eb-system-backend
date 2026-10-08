from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="systemuser",
            options={
                "verbose_name": "Usuário do Sistema",
                "verbose_name_plural": "Usuários do Sistema",
            },
        ),
    ]
