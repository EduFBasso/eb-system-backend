from django.db import migrations


class Migration(migrations.Migration):
    """State-only removal: TelegramProfessionalLink now lives in apps.notifications.

    No database_operations here — the physical table is untouched, only Django's
    migration state is updated to stop tracking the model under apps.clinic.
    """

    dependencies = [
        ('clinic', '0004_podologyprocedurecontext'),
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='TelegramProfessionalLink'),
            ],
        ),
    ]
