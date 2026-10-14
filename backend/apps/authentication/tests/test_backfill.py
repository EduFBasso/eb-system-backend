import pytest

from apps.authentication.models import SystemUser, Tenant, TenantMembership
from apps.authentication.services.backfill import (
    DIRECT_MODEL_SPECS,
    DERIVED_MODEL_SPECS,
    _tenant_by_professional,
)
from django.apps import apps


@pytest.mark.django_db
def test_backfill_specs_resolve_registered_models():
    for app_label, model_name, _ in [*DIRECT_MODEL_SPECS, *DERIVED_MODEL_SPECS]:
        model = apps.get_model(app_label, model_name)
        assert model._meta.app_label == app_label


@pytest.mark.django_db
def test_tenant_by_professional_maps_only_unambiguous_active_memberships():
    professional = SystemUser.objects.create_user(
        email="single-tenant@example.test",
        password="StrongPassword123!",
        first_name="Single",
        last_name="Tenant",
    )
    ambiguous = SystemUser.objects.create_user(
        email="multi-tenant@example.test",
        password="StrongPassword123!",
        first_name="Multi",
        last_name="Tenant",
    )
    tenant_a = Tenant.objects.create(
        name="Tenant A",
        trade_name="Tenant A",
        slug="tenant-a-backfill",
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={"clinic": True},
    )
    tenant_b = Tenant.objects.create(
        name="Tenant B",
        trade_name="Tenant B",
        slug="tenant-b-backfill",
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={"clinic": True},
    )
    TenantMembership.objects.create(tenant=tenant_a, professional=professional)
    TenantMembership.objects.create(tenant=tenant_a, professional=ambiguous)
    TenantMembership.objects.create(tenant=tenant_b, professional=ambiguous)

    mapping = _tenant_by_professional(apps)

    assert mapping == {professional.id: tenant_a.id}
