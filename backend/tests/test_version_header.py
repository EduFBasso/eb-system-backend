import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.clinic.models.clients import Client
from apps.authentication.models import Tenant, TenantMembership

@pytest.mark.django_db
def test_version_header_present():
    c = APIClient()
    r = c.get('/health/')
    assert r.status_code == 200  # type: ignore[union-attr]
    assert 'X-App-Version' in r.headers
    assert r.headers['X-App-Version']  # non-empty


@pytest.mark.django_db
@override_settings(ONLINE_MUTATION_LOCK_ENABLED=True)
def test_online_mutation_lock_blocks_patch_but_not_get(django_user_model):
    user = django_user_model.objects.create_user(
        email='lock@example.com',
        password='secret123',
        first_name='Lock',
        last_name='Tester',
    )
    tenant = Tenant.objects.create(name='Tenant Lock', slug=f'tenant-lock-{user.pk}')
    TenantMembership.objects.create(tenant=tenant, professional=user, role=TenantMembership.Role.OWNER, is_active=True)
    client_obj = Client.objects.create(
        tenant=tenant,
        first_name='Cliente',
        last_name='Travado',
        phone='11999999992',
    )
    c = APIClient()
    c.force_authenticate(user=user)

    get_response = c.get('/health/')
    patch_response = c.patch(
        f'/register/clients/{client_obj.id}/',
        data='{"first_name":"Atualizado"}',
        content_type='application/json',
    )

    assert get_response.status_code == 200
    assert patch_response.status_code == 423
