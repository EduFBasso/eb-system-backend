from django.db import transaction

from apps.authentication.models import ProfessionalSettings
from apps.authentication.services.permissions import (
    get_tenant_membership_from_request,
)
from apps.clinic.models import ClinicProfessionalProfile, ClinicProfessionalSettings


def get_or_create_clinic_profile(user, tenant):
    with transaction.atomic():
        profile, _profile_created = ClinicProfessionalProfile.objects.get_or_create(
            system_user=user,
            tenant=tenant,
            defaults={
                "register_number": user.register_number,
                "specialty": user.specialty,
            },
        )
        legacy_settings = ProfessionalSettings.objects.filter(
            professional_id=user.id
        ).first()
        profile_settings, settings_created = (
            ClinicProfessionalSettings.objects.get_or_create(
                professional=profile,
                defaults={
                    "lock_odonto_plan_after_print": user.lock_odonto_plan_after_print,
                    "odonto_quote_validity_days": user.odonto_quote_validity_days,
                },
            )
        )
        if settings_created and legacy_settings:
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
            profile_settings.save()
    return profile


def get_active_clinic_profile(request):
    auth_token = getattr(request, "auth", None)
    if auth_token is not None and auth_token.get("ecosystem") != "clinic":
        return None
    membership = get_tenant_membership_from_request(request, ecosystem="clinic")
    if not membership:
        return None
    return get_or_create_clinic_profile(request.user, membership.tenant)
