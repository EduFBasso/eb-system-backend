import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.clients import Client
from apps.clinic.models.treatment import TreatmentPlan


pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    professional = Professional.objects.create_user(
        email='print-preference@example.com',
        password='secret123',
        first_name='Print',
        last_name='Preference',
    )
    tenant = Tenant.objects.create(
        name='Odonto Print Tenant',
        slug='odonto-print-tenant',
        capabilities={'clinic': True, 'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def api_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def client_obj(owner):
    tenant = owner.tenant_memberships.first().tenant
    return Client.objects.create(
        tenant=tenant,
        first_name='Paciente',
        last_name='Odonto',
        phone='11999990000',
    )


def make_plan(owner, client_obj, **kwargs):
    return TreatmentPlan.objects.create(
        tenant=owner.tenant_memberships.first().tenant,
        professional=owner,
        client=client_obj,
        name='Plano de teste',
        **kwargs,
    )


def test_profile_api_persists_print_preferences(api_client, owner):
    response = api_client.patch(
        '/register/professionals/me/',
        {
            'lock_odonto_plan_after_print': False,
            'odonto_quote_validity_days': 45,
        },
        format='json',
    )

    assert response.status_code == 200, response.content
    assert response.json()['lock_odonto_plan_after_print'] is False
    assert response.json()['odonto_quote_validity_days'] == 45
    owner.refresh_from_db()
    assert owner.lock_odonto_plan_after_print is False
    assert owner.odonto_quote_validity_days == 45


def test_printing_without_lock_preference_keeps_plan_editable(api_client, owner, client_obj):
    owner.lock_odonto_plan_after_print = False
    owner.save(update_fields=['lock_odonto_plan_after_print'])
    plan = make_plan(owner, client_obj)

    response = api_client.post(f'/clinic/treatment/plans/{plan.id}/mark-printed/')

    assert response.status_code == 200, response.content
    plan.refresh_from_db()
    assert plan.is_printed is False
    assert plan.printed_at is None


def test_printing_with_lock_preference_locks_plan(api_client, owner, client_obj):
    plan = make_plan(owner, client_obj)

    response = api_client.post(f'/clinic/treatment/plans/{plan.id}/mark-printed/')

    assert response.status_code == 200, response.content
    plan.refresh_from_db()
    assert plan.is_printed is True
    assert plan.printed_at is not None


def test_disabling_preference_does_not_unlock_existing_plan(api_client, owner, client_obj):
    plan = make_plan(owner, client_obj, is_printed=True)
    owner.lock_odonto_plan_after_print = False
    owner.save(update_fields=['lock_odonto_plan_after_print'])

    response = api_client.patch(
        f'/clinic/treatment/plans/{plan.id}/',
        {'name': 'Tentativa de alteração'},
        format='json',
    )

    assert response.status_code == 403, response.content
