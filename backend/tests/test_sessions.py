import pytest
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from apps.authentication.models import Professional, DeviceSession


@pytest.fixture
def professional(db):
    return Professional.objects.create_user(
        email='pro1@example.com',
        password='senha123',
        first_name='Pro',
        last_name='One'
    )


@pytest.fixture
def auth_client(client, professional):
    refresh = RefreshToken.for_user(professional)
    access = str(refresh.access_token)
    client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {access}'
    client.defaults['HTTP_X_DEVICE_ID'] = 'test-device'
    client.defaults['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
    return client


def test_sessions_summary_creates_session(auth_client, professional):
    r = auth_client.get('/sessions/summary')
    assert r.status_code == 200
    body = r.json()
    assert 'count' in body and 'has_others' in body
    assert body['count'] == 1
    assert DeviceSession.objects.filter(professional=professional, device_id='test-device').exists()


def test_sessions_active_lists_current(auth_client):
    r = auth_client.get('/sessions/active')
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    assert len(arr) == 1
    assert arr[0]['is_current'] is True
    assert arr[0]['device_id'] == 'test-device'
    # Novos campos
    assert 'device_type' in arr[0]
    assert 'os' in arr[0]
    assert 'browser' in arr[0]


def test_sessions_revoke_other(auth_client, professional):
    # Criar outra sessão manualmente
    DeviceSession.objects.create(
        professional=professional,
        device_id='other-device',
        user_agent='test',
        ip_address='127.0.0.1'
    )
    r_sum = auth_client.get('/sessions/summary')
    assert r_sum.json()['count'] == 2

    r_rev = auth_client.post('/sessions/revoke', {'mode': 'all_except_current'}, content_type='application/json')
    assert r_rev.status_code == 200
    assert r_rev.json()['revoked'] == 1

    # Agora apenas a atual deve permanecer ativa
    r_sum2 = auth_client.get('/sessions/summary')
    assert r_sum2.json()['count'] == 1


def test_sessions_revoke_single(auth_client, professional):
    # Criar mais duas sessões
    from apps.authentication.models import DeviceSession
    s2 = DeviceSession.objects.create(
        professional=professional,
        device_id='other-device-1',
        user_agent='test',
        ip_address='127.0.0.1'
    )
    s3 = DeviceSession.objects.create(
        professional=professional,
        device_id='other-device-2',
        user_agent='test',
        ip_address='127.0.0.1'
    )
    r_sum = auth_client.get('/sessions/summary')
    assert r_sum.json()['count'] == 3
    # Revogar apenas s2
    r_single = auth_client.post('/sessions/revoke', { 'session_id': str(s2.id) }, content_type='application/json')
    assert r_single.status_code == 200
    body = r_single.json()
    assert body['revoked'] == 1 and body['mode'] == 'single'
    # Verificar counts
    r_sum2 = auth_client.get('/sessions/summary')
    assert r_sum2.json()['count'] == 2
    # Garantir que s2 está terminada e s3 permanece
    s2.refresh_from_db()
    s3.refresh_from_db()
    assert s2.is_active is False
    assert s3.is_active is True