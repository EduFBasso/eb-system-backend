import pytest

from apps.register.models import Professional
from apps.tenancy.models import TenantMembership


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "specialty",
    [
        "Odonto",
        "Dentista",
        "Ortodontia",
    ],
)
def test_signal_sets_odonto_capability_for_supported_specialties(specialty):
    professional = Professional.objects.create_user(
        email=f"{specialty.lower()}@example.com",
        password="secret123",
        first_name="Prof",
        last_name="Odonto",
        specialty=specialty,
    )

    membership = TenantMembership.objects.select_related("tenant").get(
        professional=professional
    )

    assert membership.role == TenantMembership.Role.ADMIN
    assert membership.is_active is True
    assert membership.tenant.capabilities == {"odonto": True}


def test_signal_creates_tenant_and_admin_membership_without_odonto_capability():
    professional = Professional.objects.create_user(
        email="podologia@example.com",
        password="secret123",
        first_name="Regiane",
        last_name="Podologa",
        specialty="Podologia",
    )

    membership = TenantMembership.objects.select_related("tenant").get(
        professional=professional
    )

    assert membership.role == TenantMembership.Role.ADMIN
    assert membership.is_active is True
    assert membership.tenant.capabilities == {}
    assert membership.tenant.slug.startswith(f"professional-{professional.pk}-")


def test_signal_is_idempotent_on_professional_update():
    professional = Professional.objects.create_user(
        email="update-check@example.com",
        password="secret123",
        first_name="Bruna",
        last_name="Dentista",
        specialty="Odontologia",
    )

    initial_membership_count = TenantMembership.objects.filter(
        professional=professional
    ).count()
    initial_tenant_ids = list(
        TenantMembership.objects.filter(professional=professional).values_list(
            "tenant_id", flat=True
        )
    )

    professional.first_name = "Bruna Atualizada"
    professional.save(update_fields=["first_name"])

    assert (
        TenantMembership.objects.filter(professional=professional).count()
        == initial_membership_count
    )
    assert list(
        TenantMembership.objects.filter(professional=professional).values_list(
            "tenant_id", flat=True
        )
    ) == initial_tenant_ids
