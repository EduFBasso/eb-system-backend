import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.clients import Client
from apps.clinic.models.odonto import TreatmentPlan


pytestmark = pytest.mark.django_db


def make_professional(email: str, specialty: str):
    professional = Professional.objects.create_user(
        email=email,
        password='secret123',
        first_name='Test',
        last_name=specialty,
        specialty=specialty,
    )
    tenant = Tenant.objects.create(
        name=f'Tenant {specialty}',
        slug=f'tenant-{specialty.lower()}',
        capabilities={'clinic': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional, tenant


def test_treatment_plans_are_available_without_specialty_capability():
    professional, tenant = make_professional('podologia-plan@example.com', 'Podologia')
    client = Client.objects.create(
        tenant=tenant,
        first_name='Paciente',
        last_name='Teste',
        phone='11999990000',
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/treatment/plans/',
        {'client': client.id, 'name': 'Plano clínico', 'status': 'pending'},
        format='json',
    )

    assert response.status_code == 201, response.content
    assert TreatmentPlan.objects.filter(professional=professional, client=client).exists()


def test_treatment_plan_list_remains_professional_scoped():
    owner, tenant = make_professional('owner-plan@example.com', 'Podologia')
    other, other_tenant = make_professional('other-plan@example.com', 'Odontologia')
    owner_client = Client.objects.create(tenant=tenant, first_name='Owner', last_name='Client', phone='11999990001')
    other_client = Client.objects.create(tenant=other_tenant, first_name='Other', last_name='Client', phone='11999990002')
    owner_plan = TreatmentPlan.objects.create(tenant=tenant, professional=owner, client=owner_client)
    other_plan = TreatmentPlan.objects.create(tenant=other_tenant, professional=other, client=other_client)
    api = APIClient()
    api.force_authenticate(user=owner)

    response = api.get('/treatment/plans/')

    assert response.status_code == 200, response.content
    ids = {row['id'] for row in response.json()}
    assert owner_plan.id in ids
    assert other_plan.id not in ids
