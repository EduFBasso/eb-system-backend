from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('authentication', '0002_professional_address_professional_cnpj_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='professional',
            name='lock_odonto_plan_after_print',
            field=models.BooleanField(
                default=True,
                help_text='Quando ativo, a impressão de um plano odontológico bloqueia novas edições.',
                verbose_name='Bloquear plano odontológico após impressão',
            ),
        ),
    ]
