import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership


@pytest.mark.django_db
def test_clinic_specialty_routes_are_exposed():
    professional = Professional.objects.create_user(
        email='specialty-owner@example.com',
        password='secret123',
        first_name='Specialty',
        last_name='Owner',
        specialty='Podologia',
    )
    tenant = Tenant.objects.create(
        name='Clinic Tenant',
        slug='clinic-tenant',
        capabilities={'clinic': True, 'podologia': True, 'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=professional)

    podology_response = client.get('/clinic/podology/anamnesis/fields/')
    assert podology_response.status_code == 200, podology_response.content

    odonto_response = client.get('/clinic/odonto/arcades/')
    assert odonto_response.status_code in {200, 403}, odonto_response.content
