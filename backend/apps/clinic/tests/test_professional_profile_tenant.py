import pytest
from rest_framework.test import APIRequestFactory

from apps.authentication.models import SystemUser, Tenant, TenantMembership
from apps.clinic.models import ClinicProfessionalProfile, ClinicProfessionalSettings
from apps.clinic.services.professionals import get_active_clinic_profile


@pytest.mark.django_db
def test_active_clinic_profile_uses_tenant_from_token():
    user = SystemUser.objects.create_user(
        email="multi-clinic@example.com",
        password="senha-segura-123",
    )
    first_tenant = Tenant.objects.create(
        name="Clinic A",
        slug="clinic-a-profile",
        ecosystem=Tenant.Ecosystem.CLINIC,
    )
    second_tenant = Tenant.objects.create(
        name="Clinic B",
        slug="clinic-b-profile",
        ecosystem=Tenant.Ecosystem.CLINIC,
    )
    TenantMembership.objects.create(
        tenant=first_tenant,
        professional=user,
        role=TenantMembership.Role.OWNER,
    )
    TenantMembership.objects.create(
        tenant=second_tenant,
        professional=user,
        role=TenantMembership.Role.OWNER,
    )
    ClinicProfessionalProfile.objects.create(
        system_user=user,
        tenant=first_tenant,
        specialty="Podologia",
    )

    request = APIRequestFactory().get("/")
    request.user = user
    request.auth = {
        "tenant_id": second_tenant.id,
        "ecosystem": Tenant.Ecosystem.CLINIC,
    }

    profile = get_active_clinic_profile(request)

    assert profile is not None
    assert profile.tenant_id == second_tenant.id


@pytest.mark.django_db
def test_active_clinic_profile_rejects_non_clinic_token():
    user = SystemUser.objects.create_user(
        email="bakery-token@example.com",
        password="senha-segura-123",
    )
    tenant = Tenant.objects.create(
        name="Clinic",
        slug="clinic-profile-token",
        ecosystem=Tenant.Ecosystem.CLINIC,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=TenantMembership.Role.OWNER,
    )

    request = APIRequestFactory().get("/")
    request.user = user
    request.auth = {
        "tenant_id": tenant.id,
        "ecosystem": Tenant.Ecosystem.BAKERY,
    }

    assert get_active_clinic_profile(request) is None


@pytest.mark.django_db
def test_active_clinic_profile_repairs_missing_settings():
    user = SystemUser.objects.create_user(
        email="missing-settings@example.com",
        password="senha-segura-123",
    )
    tenant = Tenant.objects.create(
        name="Clinic",
        slug="clinic-missing-settings",
        ecosystem=Tenant.Ecosystem.CLINIC,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=TenantMembership.Role.OWNER,
    )
    profile = ClinicProfessionalProfile.objects.create(
        system_user=user,
        tenant=tenant,
    )

    request = APIRequestFactory().get("/")
    request.user = user
    request.auth = {
        "tenant_id": tenant.id,
        "ecosystem": Tenant.Ecosystem.CLINIC,
    }

    resolved_profile = get_active_clinic_profile(request)

    assert resolved_profile.id == profile.id
    assert ClinicProfessionalSettings.objects.filter(
        professional=profile,
    ).exists()
