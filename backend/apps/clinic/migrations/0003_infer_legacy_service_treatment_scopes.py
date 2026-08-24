from django.db import migrations


def infer_legacy_treatment_scopes(apps, schema_editor):
    Service = apps.get_model('clinic', 'Service')
    TreatmentPlanItem = apps.get_model('clinic', 'TreatmentPlanItem')

    for service in Service.objects.filter(treatment_scopes=[]).iterator():
        legacy_items = TreatmentPlanItem.objects.filter(
            service__isnull=True,
            custom_name__iexact=service.name,
            plan__tenant_id=service.tenant_id,
        )
        context_scopes = set(
            legacy_items.filter(dental_context__isnull=False).values_list(
                'dental_context__scope', flat=True
            )
        )
        scopes = []
        if 'tooth' in context_scopes:
            scopes.append('tooth')
        if 'arch' in context_scopes or 'full' in context_scopes:
            scopes.append('arch')
        if legacy_items.filter(dental_context__isnull=True).exists():
            scopes.append('other')
        if scopes:
            service.treatment_scopes = scopes
            service.save(update_fields=['treatment_scopes'])


class Migration(migrations.Migration):
    dependencies = [
        ('clinic', '0002_service_treatment_scopes'),
    ]

    operations = [
        migrations.RunPython(
            infer_legacy_treatment_scopes,
            migrations.RunPython.noop,
        ),
    ]