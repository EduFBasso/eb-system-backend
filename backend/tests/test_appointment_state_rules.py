import pytest
from django.utils import timezone

from apps.clinic.models.agenda import Appointment
from apps.clinic.models.clients import Client


@pytest.mark.django_db
def test_patch_cannot_transition_status(client, django_user_model):
    pro = django_user_model.objects.create_user(
        email='state1@example.com',
        password='x',
        first_name='State',
        last_name='One',
    )
    client.force_login(pro)
    now = timezone.now()
    c = Client.objects.create(professional=pro, first_name='Cliente', last_name='Teste')

    appt = Appointment.objects.create(
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
    now = timezone.now()
    c = Client.objects.create(professional=pro, first_name='Cliente', last_name='Pendente')

    overdue = Appointment.objects.create(
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
