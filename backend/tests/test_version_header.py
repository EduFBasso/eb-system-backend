import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.clinic.models.clients import Client

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
    client_obj = Client.objects.create(
        professional=user,
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
