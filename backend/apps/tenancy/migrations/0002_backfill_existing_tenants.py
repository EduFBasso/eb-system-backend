from django.db import migrations


def backfill_existing_tenants(apps, schema_editor):
    from apps.tenancy.backfill import backfill_existing_tenants as run_backfill

    run_backfill(apps)


def clear_backfilled_tenants(apps, schema_editor):
    model_specs = [
        ('clients', 'Client'),
        ('agenda', 'Appointment'),
        ('agenda', 'FinalizeAudit'),
        ('agenda', 'Encounter'),
        ('agenda', 'ClinicalRecord'),
        ('agenda', 'Charge'),
        ('agenda', 'ChargeItem'),
        ('odonto', 'DentalArcade'),
        ('odonto', 'Tooth'),
        ('odonto', 'Surface'),
        ('odonto', 'Procedure'),
        ('odonto', 'ProcedureNameSuggestion'),
        ('odonto', 'ProductCatalogItem'),
    ]

    for app_label, model_name in model_specs:
        Model = apps.get_model(app_label, model_name)
        Model.objects.update(tenant=None)


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0001_initial'),
        ('clients', '0006_client_tenant'),
        ('agenda', '0015_appointment_tenant_charge_tenant_chargeitem_tenant_and_more'),
        ('odonto', '0008_dentalarcade_tenant_procedure_tenant_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_existing_tenants, clear_backfilled_tenants),
    ]