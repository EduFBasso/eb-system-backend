import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.clients import Client
from apps.clinic.models.podologia import PodologyProcedureContext
from apps.clinic.models.treatment import TreatmentPlan, TreatmentPlanItem


pytestmark = pytest.mark.django_db


def make_professional(email: str):
    professional = Professional.objects.create_user(
        email=email,
        password='secret123',
        first_name='Test',
        last_name='Podologia',
        specialty='Podologia',
    )
    tenant = Tenant.objects.create(
        name=f'Tenant {email}',
        slug=f"tenant-{email.split('@')[0]}",
        capabilities={'clinic': True, 'podologia': True},
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


def test_podology_context_is_created_via_treatment_item():
    professional, tenant = make_professional('podologia-item@example.com')
    client = Client.objects.create(tenant=tenant, first_name='Paciente', last_name='Pe', phone='11999990010')
    plan = make_plan(professional, tenant, client)
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
    item = TreatmentPlanItem.objects.get(id=response.json()['id'])
    context = PodologyProcedureContext.objects.get(treatment_plan_item=item)
    assert context.scope == 'pe_esquerdo'
    assert context.location_number == 1
    assert context.tenant_id == tenant.id


def test_podology_context_is_updated_via_treatment_item():
    professional, tenant = make_professional('podologia-update@example.com')
    client = Client.objects.create(tenant=tenant, first_name='Paciente', last_name='Pe', phone='11999990011')
    plan = make_plan(professional, tenant, client)
    item = TreatmentPlanItem.objects.create(plan=plan, custom_name='Calo', patient_price='50.00')
    PodologyProcedureContext.objects.create(
        treatment_plan_item=item, tenant=tenant, scope='pe_direito', location_number=2
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.patch(
        f'/clinic/treatment/items/{item.id}/',
        {'podology_context': {'scope': 'mao_esquerda', 'location_number': 3}},
        format='json',
    )

    assert response.status_code == 200, response.content
    item.podology_context.refresh_from_db()
    assert item.podology_context.scope == 'mao_esquerda'
    assert item.podology_context.location_number == 3


def test_item_cannot_have_both_dental_and_podology_context():
    professional, tenant = make_professional('mixed-context@example.com')
    client = Client.objects.create(tenant=tenant, first_name='Paciente', last_name='Misto', phone='11999990012')
    plan = make_plan(professional, tenant, client)
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/items/',
        {
            'plan': plan.id,
            'kind': 'service',
            'custom_name': 'Procedimento misto',
            'dental_context': {'scope': 'tooth', 'tooth_number': 11},
            'podology_context': {'scope': 'pe_esquerdo', 'location_number': 1},
        },
        format='json',
    )

    assert response.status_code == 400, response.content


def test_podology_items_remain_professional_scoped():
    owner, owner_tenant = make_professional('owner-podology@example.com')
    other, other_tenant = make_professional('other-podology@example.com')
    owner_client = Client.objects.create(
        tenant=owner_tenant, first_name='Owner', last_name='Client', phone='11999990013'
    )
    other_client = Client.objects.create(
        tenant=other_tenant, first_name='Other', last_name='Client', phone='11999990014'
    )
    owner_plan = make_plan(owner, owner_tenant, owner_client)
    other_plan = make_plan(other, other_tenant, other_client)
    owner_item = TreatmentPlanItem.objects.create(plan=owner_plan, custom_name='Item do owner', patient_price='10.00')
    other_item = TreatmentPlanItem.objects.create(plan=other_plan, custom_name='Item do outro', patient_price='10.00')
    PodologyProcedureContext.objects.create(treatment_plan_item=owner_item, tenant=owner_tenant, scope='geral')
    PodologyProcedureContext.objects.create(treatment_plan_item=other_item, tenant=other_tenant, scope='geral')

    api = APIClient()
    api.force_authenticate(user=owner)

    response = api.get(f'/clinic/treatment/items/?plan={owner_plan.id}')
    assert response.status_code == 200, response.content
    ids = {row['id'] for row in response.json()}
    assert owner_item.id in ids

    other_response = api.get(f'/clinic/treatment/items/?plan={other_plan.id}')
    assert other_response.status_code == 200, other_response.content
    assert other_response.json() == []
