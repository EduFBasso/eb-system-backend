from django.db import migrations, models


def infer_treatment_scopes(apps, schema_editor):
    Service = apps.get_model('clinic', 'Service')
    TreatmentPlanItem = apps.get_model('clinic', 'TreatmentPlanItem')

    for service in Service.objects.all().iterator():
        service_items = TreatmentPlanItem.objects.filter(service_id=service.id)
        context_scopes = set(
            service_items.filter(dental_context__isnull=False).values_list(
                'dental_context__scope', flat=True
            )
        )
        scopes = []
        if 'tooth' in context_scopes:
            scopes.append('tooth')
        if 'arch' in context_scopes or 'full' in context_scopes:
            scopes.append('arch')
        if service_items.filter(dental_context__isnull=True).exists():
            scopes.append('other')
        if scopes:
            service.treatment_scopes = scopes
            service.save(update_fields=['treatment_scopes'])


class Migration(migrations.Migration):
    dependencies = [
        ('clinic', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='treatment_scopes',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Categorias permitidas no plano: tooth, arch ou other.',
                verbose_name='Subcategorias de Tratamento',
            ),
        ),
        migrations.RunPython(infer_treatment_scopes, migrations.RunPython.noop),
    ]