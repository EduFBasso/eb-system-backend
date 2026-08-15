import pytest
from django.utils import timezone

from apps.clinic.models.agenda import Appointment
from apps.clinic.models.clients import Client
from apps.authentication.models import Tenant, TenantMembership


def _setup_tenant(professional):
    tenant = Tenant.objects.create(
        name=f'Tenant {professional.pk}',
        slug=f'tenant-state-{professional.pk}',
    )
    TenantMembership.objects.create(
        tenant=tenant, professional=professional,
        role=TenantMembership.Role.OWNER, is_active=True,
    )
    return tenant


@pytest.mark.django_db
def test_patch_cannot_transition_status(client, django_user_model):
    pro = django_user_model.objects.create_user(
        email='state1@example.com',
        password='x',
        first_name='State',
        last_name='One',
    )
    client.force_login(pro)
    tenant = _setup_tenant(pro)
    now = timezone.now()
    c = Client.objects.create(tenant=tenant, first_name='Cliente', last_name='Teste', phone='11900000001')

    appt = Appointment.objects.create(
        tenant=tenant,
        professional=pro,
        client=c,
        title='Consulta',
        start_at=now + timezone.timedelta(minutes=20),
        end_at=now + timezone.timedelta(minutes=50),
        status=Appointment.Status.SCHEDULED,
    )

    resp = client.patch(
        f'/agenda/appointments/{appt.id}/',
        data='{"status":"done"}',
        content_type='application/json',
    )

    assert resp.status_code == 400
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.SCHEDULED


@pytest.mark.django_db
def test_create_promotes_overdue_to_pending_and_blocks_new_schedule(
    client,
    django_user_model,
):
    pro = django_user_model.objects.create_user(
        email='state2@example.com',
        password='x',
        first_name='State',
        last_name='Two',
    )
    client.force_login(pro)
    tenant = _setup_tenant(pro)
    now = timezone.now()
    c = Client.objects.create(tenant=tenant, first_name='Cliente', last_name='Pendente', phone='11900000002')

    overdue = Appointment.objects.create(
        tenant=tenant,
        professional=pro,
        client=c,
        title='Sessão anterior',
        start_at=now - timezone.timedelta(hours=2),
        end_at=now - timezone.timedelta(hours=1, minutes=30),
        status=Appointment.Status.SCHEDULED,
    )

    payload = {
        'client': c.id,
        'title': 'Nova sessão',
        'visit_type': 'consulta',
        'start_at': (now + timezone.timedelta(days=1)).isoformat(),
        'end_at': (now + timezone.timedelta(days=1, minutes=30)).isoformat(),
    }

    resp = client.post('/agenda/appointments/', payload, content_type='application/json')

    assert resp.status_code == 400
    overdue.refresh_from_db()
    assert overdue.status == Appointment.Status.PENDING


@pytest.mark.django_db
def test_expired_appointment_pending_then_done_is_idempotent(client, django_user_model):
    pro = django_user_model.objects.create_user(
        email='state3@example.com',
        password='x',
        first_name='State',
        last_name='Three',
    )
    client.force_login(pro)
    tenant = _setup_tenant(pro)
    now = timezone.now()
    customer = Client.objects.create(
        tenant=tenant,
        first_name='Cliente',
        last_name='Concluído',
        phone='11900000003',
    )
    appointment = Appointment.objects.create(
        tenant=tenant,
        professional=pro,
        client=customer,
        title='Consulta expirada',
        start_at=now - timezone.timedelta(hours=2),
        end_at=now - timezone.timedelta(hours=1),
        status=Appointment.Status.SCHEDULED,
    )

    # A leitura da agenda aplica a promoção temporal scheduled -> pending.
    list_response = client.get('/agenda/appointments/')
    assert list_response.status_code == 200, list_response.content
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.PENDING

    done_response = client.post(f'/agenda/appointments/{appointment.id}/done/')
    assert done_response.status_code == 200, done_response.content
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.DONE

    # Concluir novamente é idempotente.
    repeated_done_response = client.post(
        f'/agenda/appointments/{appointment.id}/done/'
    )
    assert repeated_done_response.status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.DONE
