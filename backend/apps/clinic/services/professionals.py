from apps.authentication.models import ProfessionalSettings
from apps.authentication.services.permissions import (
    get_tenant_membership_from_request,
)
from apps.clinic.models import ClinicProfessionalProfile, ClinicProfessionalSettings


def get_or_create_clinic_profile(user, tenant):
    profile, created = ClinicProfessionalProfile.objects.get_or_create(
        system_user=user,
        tenant=tenant,
        defaults={
            "register_number": user.register_number,
            "specialty": user.specialty,
        },
    )
    if created:
        legacy_settings = ProfessionalSettings.objects.filter(
            professional_id=user.id
        ).first()
        settings = ClinicProfessionalSettings.objects.create(
            professional=profile,
            lock_odonto_plan_after_print=user.lock_odonto_plan_after_print,
            odonto_quote_validity_days=user.odonto_quote_validity_days,
        )
        if legacy_settings:
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
                setattr(settings, field, getattr(legacy_settings, field))
            settings.save()
    return profile


def get_active_clinic_profile(request):
    auth_token = getattr(request, "auth", None)
    if auth_token is not None and auth_token.get("ecosystem") != "clinic":
        return None
    membership = get_tenant_membership_from_request(request, ecosystem="clinic")
    if not membership:
        return None
    return get_or_create_clinic_profile(request.user, membership.tenant)
