import pytest
from io import StringIO
from django.core.management import call_command

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

    direct_model_names = {model_name for _, model_name, _ in DIRECT_MODEL_SPECS}
    derived_model_names = {model_name for _, model_name, _ in DERIVED_MODEL_SPECS}
    assert "AnamnesePodologia" not in direct_model_names | derived_model_names
    assert "AnamneseOdontologia" not in direct_model_names | derived_model_names
    assert "DentalProcedureContext" not in direct_model_names | derived_model_names

    for app_label, model_name, _ in [*DIRECT_MODEL_SPECS, *DERIVED_MODEL_SPECS]:
        model = apps.get_model(app_label, model_name)
        assert model._meta.get_field("tenant").name == "tenant"


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


@pytest.mark.django_db
def test_backfill_command_supports_dry_run_without_writes():
    output = StringIO()

    call_command("backfill_existing_tenants", "--dry-run", stdout=output)

    assert "Backfill de tenants (dry-run):" in output.getvalue()
