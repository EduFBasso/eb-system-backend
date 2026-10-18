from django.db import migrations


def backfill_profiles(apps, schema_editor):
    Tenant = apps.get_model("authentication", "Tenant")
    Membership = apps.get_model("authentication", "TenantMembership")
    Profile = apps.get_model("clinic", "ClinicProfessionalProfile")
    Settings = apps.get_model("clinic", "ClinicProfessionalSettings")
    LegacySettings = apps.get_model("authentication", "ProfessionalSettings")

    clinic_tenants = Tenant.objects.filter(ecosystem="clinic")
    for membership in Membership.objects.filter(
        tenant__in=clinic_tenants,
        is_active=True,
    ).select_related("tenant", "professional"):
        user = membership.professional
        profile, _ = Profile.objects.get_or_create(
            system_user_id=user.id,
            tenant_id=membership.tenant_id,
            defaults={
                "register_number": user.register_number,
                "specialty": user.specialty,
                "is_active": user.is_active,
            },
        )
        legacy = LegacySettings.objects.filter(professional_id=user.id).first()
        defaults = {
            "lock_odonto_plan_after_print": user.lock_odonto_plan_after_print,
            "odonto_quote_validity_days": user.odonto_quote_validity_days,
        }
        if legacy:
            for field in (
                "work_start_hour",
                "work_start_minute",
                "work_end_hour",
                "work_end_minute",
                "slot_minutes",
                "default_duration_minutes",
                "default_visit_type",
                "confirm_message_enabled",
                "confirm_message_template",
                "reminder_enabled",
                "reminder_minutes_before",
            ):
                defaults[field] = getattr(legacy, field)
        Settings.objects.get_or_create(professional_id=profile.id, defaults=defaults)


class Migration(migrations.Migration):
    dependencies = [
        ("clinic", "0002_clinicprofessionalprofile_clinicprofessionalsettings_and_more"),
        ("authentication", "0007_alter_tenant_ecosystem"),
    ]

    operations = [migrations.RunPython(backfill_profiles, migrations.RunPython.noop)]
