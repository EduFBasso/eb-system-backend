import pytest

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.bakery.validators import has_duplicate_bakery_owner_name


@pytest.mark.django_db
def test_bakery_owner_name_is_unique_across_bakery_memberships():
    first_owner = Professional.objects.create_user(
        email="first-owner@bakery.test",
        password="secret123",
        first_name="Ana",
        last_name="Padeiro",
    )
    bakery_tenant = Tenant.objects.create(
        name="Padaria Central",
        slug="padaria-central-validator",
        ecosystem=Tenant.Ecosystem.BAKERY,
    )
    TenantMembership.objects.create(
        tenant=bakery_tenant,
        professional=first_owner,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    assert has_duplicate_bakery_owner_name("ana", "padeiro")
    assert not has_duplicate_bakery_owner_name(
        "Ana",
        "Padeiro",
        exclude_professional_id=first_owner.id,
    )


@pytest.mark.django_db
def test_same_owner_name_is_allowed_in_clinic_tenant():
    clinic_owner = Professional.objects.create_user(
        email="clinic-owner@clinic.test",
        password="secret123",
        first_name="Ana",
        last_name="Padeiro",
    )
    clinic_tenant = Tenant.objects.create(
        name="Clínica Central",
        slug="clinica-central-validator",
        ecosystem=Tenant.Ecosystem.CLINIC,
    )
    TenantMembership.objects.create(
        tenant=clinic_tenant,
        professional=clinic_owner,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    assert not has_duplicate_bakery_owner_name("Ana", "Padeiro")
