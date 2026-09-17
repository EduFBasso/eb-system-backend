import pytest

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.authentication.services import (
    get_active_tenant_membership,
    user_has_tenant_capability,
)


@pytest.fixture
def professional(db):
    return Professional.objects.create_user(
        email="permissions@example.com",
        password="secret123",
        first_name="Permission",
        last_name="Tester",
    )


@pytest.fixture
def clinic_tenant(db):
    return Tenant.objects.create(
        name="Clinic Permissions",
        slug="clinic-permissions",
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={"clinic": True, "odonto": True},
        is_active=True,
    )


@pytest.mark.django_db
def test_active_membership_can_be_filtered_by_ecosystem(professional, clinic_tenant):
    membership = TenantMembership.objects.create(
        tenant=clinic_tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
        is_active=True,
    )

    assert get_active_tenant_membership(professional, ecosystem="clinic") == membership
    assert get_active_tenant_membership(professional, ecosystem="bakery") is None


@pytest.mark.django_db
def test_capability_comes_from_active_tenant(professional, clinic_tenant):
    TenantMembership.objects.create(
        tenant=clinic_tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
        is_active=True,
    )

    assert user_has_tenant_capability(professional, "odonto", ecosystem="clinic")
    assert not user_has_tenant_capability(professional, "podologia", ecosystem="clinic")


@pytest.mark.django_db
def test_inactive_membership_does_not_grant_capability(professional, clinic_tenant):
    TenantMembership.objects.create(
        tenant=clinic_tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
        is_active=False,
    )

    assert get_active_tenant_membership(professional, ecosystem="clinic") is None
    assert not user_has_tenant_capability(professional, "odonto", ecosystem="clinic")


@pytest.mark.django_db
def test_superuser_bypasses_capability_check(db):
    superuser = Professional.objects.create_superuser(
        email="superuser-permissions@example.com",
        password="secret123",
    )

    assert user_has_tenant_capability(superuser, "any-capability", ecosystem="clinic")
