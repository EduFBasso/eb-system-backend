import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.clients import Client
from apps.clinic.models.inventory import Product, Service
from apps.clinic.models.treatment import TreatmentPlan, TreatmentPlanItem


pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog_context():
    professional = Professional.objects.create_user(
        email='catalog-delete@example.com',
        password='secret123',
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Catalog Delete', slug='catalog-delete')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    client = Client.objects.create(
        tenant=tenant,
        first_name='Cliente',
        last_name='Catálogo',
        phone='11999999981',
    )
    plan = TreatmentPlan.objects.create(
        tenant=tenant,
        professional=professional,
        client=client,
    )
    api_client = APIClient()
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(professional)}',
    )
    return api_client, tenant, plan


def test_delete_service_preserves_name_in_treatment_item(catalog_context):
    api_client, tenant, plan = catalog_context
    service = Service.objects.create(tenant=tenant, name='Botox')
    item = TreatmentPlanItem.objects.create(
        plan=plan,
        kind=TreatmentPlanItem.ItemKind.SERVICE,
        service=service,
    )

    response = api_client.delete(f'/inventory/services/{service.id}/')

    assert response.status_code == 204, response.content
    item.refresh_from_db()
    assert item.service_id is None
    assert item.custom_name == 'Botox'


def test_delete_product_preserves_name_in_treatment_item(catalog_context):
    api_client, tenant, plan = catalog_context
    product = Product.objects.create(tenant=tenant, name='Resina tipo 1')
    item = TreatmentPlanItem.objects.create(
        plan=plan,
        kind=TreatmentPlanItem.ItemKind.PRODUCT,
        product=product,
    )

    response = api_client.delete(f'/inventory/products/{product.id}/')

    assert response.status_code == 204, response.content
    item.refresh_from_db()
    assert item.product_id is None
    assert item.custom_name == 'Resina tipo 1'


def test_delete_unprinted_plan_removes_items_permanently(catalog_context):
    api_client, tenant, plan = catalog_context
    service = Service.objects.create(tenant=tenant, name='Botox')
    product = Product.objects.create(tenant=tenant, name='Resina tipo 1')
    service_item = TreatmentPlanItem.objects.create(
        plan=plan,
        kind=TreatmentPlanItem.ItemKind.SERVICE,
        service=service,
        patient_price=500,
    )
    product_item = TreatmentPlanItem.objects.create(
        plan=plan,
        kind=TreatmentPlanItem.ItemKind.PRODUCT,
        product=product,
        patient_price=70,
    )

    response = api_client.delete(f'/clinic/treatment/plans/{plan.id}/')

    assert response.status_code == 204, response.content
    assert not TreatmentPlan.objects.filter(pk=plan.id).exists()
    assert not TreatmentPlanItem.objects.filter(
        pk__in=[service_item.id, product_item.id],
    ).exists()


def test_service_api_persists_valid_treatment_categories(catalog_context):
    api_client, _, _ = catalog_context

    response = api_client.post(
        '/inventory/services/',
        {
            'name': 'Avaliação geral',
            'base_price': '100.00',
            'treatment_scopes': ['tooth', 'arch', 'other'],
        },
        format='json',
    )

    assert response.status_code == 201, response.content
    assert response.data['treatment_scopes'] == ['tooth', 'arch', 'other']
    assert Service.objects.get(pk=response.data['id']).treatment_scopes == [
        'tooth',
        'arch',
        'other',
    ]


def test_service_api_rejects_invalid_treatment_category(catalog_context):
    api_client, _, _ = catalog_context

    response = api_client.post(
        '/inventory/services/',
        {
            'name': 'Categoria inválida',
            'treatment_scopes': ['full'],
        },
        format='json',
    )

    assert response.status_code == 400, response.content
    assert 'treatment_scopes' in response.data