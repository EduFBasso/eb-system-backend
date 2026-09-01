import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.clients import Client
from apps.clinic.models.treatment import TreatmentPlan


pytestmark = pytest.mark.django_db


def make_professional(email: str, capabilities: dict):
    professional = Professional.objects.create_user(
        email=email,
        password='secret123',
        first_name='Specialty',
        last_name='Owner',
    )
    tenant = Tenant.objects.create(
        name=f'Tenant {email}',
        slug=f"tenant-{email.split('@')[0]}",
        capabilities=capabilities,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional, tenant


def make_plan(professional, tenant, client):
    return TreatmentPlan.objects.create(tenant=tenant, professional=professional, client=client)


def test_canonical_treatment_route_is_exposed():
    """A rota única e oficial do núcleo de tratamento é '/clinic/treatment/'."""
    professional, _tenant = make_professional(
        'canonical-route@example.com', {'clinic': True, 'odonto': True}
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.get('/clinic/treatment/plans/')

    assert response.status_code == 200, response.content


def test_dental_context_requires_odonto_capability():
    professional, tenant = make_professional(
        'podologia-only@example.com', {'clinic': True, 'podologia': True}
    )
    patient = Client.objects.create(tenant=tenant, first_name='Paciente', last_name='Pe', phone='11999991000')
    plan = make_plan(professional, tenant, patient)
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/items/',
        {
            'plan': plan.id,
            'kind': 'service',
            'custom_name': 'Restauração',
            'dental_context': {'scope': 'tooth', 'tooth_number': 11},
        },
        format='json',
    )

    assert response.status_code == 400, response.content


def test_podology_context_requires_podologia_capability():
    professional, tenant = make_professional(
        'odonto-only@example.com', {'clinic': True, 'odonto': True}
    )
    patient = Client.objects.create(tenant=tenant, first_name='Paciente', last_name='Dente', phone='11999991001')
    plan = make_plan(professional, tenant, patient)
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/items/',
        {
            'plan': plan.id,
            'kind': 'service',
            'custom_name': 'Corte de unha',
            'podology_context': {'scope': 'pe_esquerdo', 'location_number': 1},
        },
        format='json',
    )

    assert response.status_code == 400, response.content


def test_dental_context_is_accepted_for_odonto_capability_tenant():
    professional, tenant = make_professional(
        'odonto-happy@example.com', {'clinic': True, 'odonto': True}
    )
    patient = Client.objects.create(tenant=tenant, first_name='Paciente', last_name='Odonto', phone='11999991002')
    plan = make_plan(professional, tenant, patient)
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/items/',
        {
            'plan': plan.id,
            'kind': 'service',
            'custom_name': 'Restauração',
            'dental_context': {'scope': 'tooth', 'tooth_number': 11},
        },
        format='json',
    )

    assert response.status_code == 201, response.content


def test_podology_context_is_accepted_for_podologia_capability_tenant():
    professional, tenant = make_professional(
        'podologia-happy@example.com', {'clinic': True, 'podologia': True}
    )
    patient = Client.objects.create(tenant=tenant, first_name='Paciente', last_name='Pe', phone='11999991003')
    plan = make_plan(professional, tenant, patient)
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/items/',
        {
            'plan': plan.id,
            'kind': 'service',
            'custom_name': 'Corte de unha',
            'podology_context': {'scope': 'pe_esquerdo', 'location_number': 1},
        },
        format='json',
    )

    assert response.status_code == 201, response.content


def test_treatment_route_keeps_tenant_isolation():
    owner, owner_tenant = make_professional('owner-route@example.com', {'clinic': True, 'odonto': True})
    other, other_tenant = make_professional('other-route@example.com', {'clinic': True, 'podologia': True})
    owner_client = Client.objects.create(
        tenant=owner_tenant, first_name='Owner', last_name='Client', phone='11999991004'
    )
    other_client = Client.objects.create(
        tenant=other_tenant, first_name='Other', last_name='Client', phone='11999991005'
    )
    owner_plan = make_plan(owner, owner_tenant, owner_client)
    other_plan = make_plan(other, other_tenant, other_client)

    api = APIClient()
    api.force_authenticate(user=owner)

    response = api.get('/clinic/treatment/plans/')

    assert response.status_code == 200, response.content
    ids = {row['id'] for row in response.json()}
    assert owner_plan.id in ids
    assert other_plan.id not in ids
