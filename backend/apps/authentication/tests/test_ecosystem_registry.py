import pytest

from apps.authentication.ecosystems import (
    REGISTRY,
    allowed_capabilities,
    ecosystem_slugs,
    get_ecosystem,
)
from apps.authentication.models import Tenant


def test_registry_matches_tenant_ecosystem_choices():
    assert set(ecosystem_slugs()) == set(Tenant.Ecosystem.values)


def test_get_ecosystem_rejects_unknown_slug():
    with pytest.raises(ValueError, match="não registrado"):
        get_ecosystem("space-station")


def test_allowed_capabilities_are_isolated_per_ecosystem():
    assert "bakery" not in allowed_capabilities("clinic")
    assert "podologia" not in allowed_capabilities("bakery")


def test_public_self_registration_flags():
    assert REGISTRY["bakery"].public_self_registration is True
    assert REGISTRY["clinic"].public_self_registration is False


def test_registry_exposes_canonical_api_prefixes():
    assert REGISTRY["clinic"].url_prefix == "/api/v1/clinic/"
    assert REGISTRY["bakery"].url_prefix == "/api/v1/bakery/"


@pytest.mark.django_db
def test_tenant_rejects_capability_from_other_ecosystem():
    with pytest.raises(ValueError, match="não pertence ao ecossistema"):
        Tenant.objects.create(
            name="Clinic With Bakery Cap",
            slug="clinic-with-bakery-cap",
            ecosystem=Tenant.Ecosystem.CLINIC,
            capabilities={"clinic": True, "bakery": True},
        )


@pytest.mark.django_db
def test_tenant_accepts_native_capabilities():
    tenant = Tenant.objects.create(
        name="Clinic Native",
        slug="clinic-native",
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={"clinic": True, "modules": {"podologia": True}},
    )
    assert tenant.pk is not None


@pytest.mark.django_db
@pytest.mark.parametrize("capabilities", [[], "clinic"])
def test_tenant_rejects_non_object_capabilities(capabilities):
    with pytest.raises(ValueError, match="deve ser um objeto JSON"):
        Tenant.objects.create(
            name="Invalid Capabilities",
            slug=f"invalid-capabilities-{type(capabilities).__name__}",
            ecosystem=Tenant.Ecosystem.CLINIC,
            capabilities=capabilities,
        )
