import pytest

from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership
from apps.tenancy.permissions import user_has_tenant_capability


pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    return Professional.objects.create_user(
        email='tenant-member@example.com',
        password='secret123',
        first_name='Tenant',
        last_name='Member',
    )


def test_user_has_capability_from_active_tenant_membership(professional):
    tenant = Tenant.objects.create(
        name='Odonto Tenant',
        slug='odonto-tenant',
        capabilities={'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
    )

    assert user_has_tenant_capability(professional, 'odonto') is True


def test_user_without_capability_is_denied(professional):
    tenant = Tenant.objects.create(
        name='Podology Tenant',
        slug='podology-tenant',
        capabilities={'podology': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
    )

    assert user_has_tenant_capability(professional, 'odonto') is False


def test_inactive_membership_is_denied(professional):
    tenant = Tenant.objects.create(
        name='Inactive Membership Tenant',
        slug='inactive-membership-tenant',
        capabilities={'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
        is_active=False,
    )

    assert user_has_tenant_capability(professional, 'odonto') is False


def test_nested_modules_capability_is_supported(professional):
    tenant = Tenant.objects.create(
        name='Nested Capability Tenant',
        slug='nested-capability-tenant',
        capabilities={'modules': {'odonto': True}},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
    )

    assert user_has_tenant_capability(professional, 'odonto') is True