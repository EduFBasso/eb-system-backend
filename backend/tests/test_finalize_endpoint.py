import pytest
from django.utils import timezone
from apps.clinic.models.agenda import Appointment
from apps.clinic.models.clients import Client


@pytest.mark.django_db
def test_finalize_too_early(client, django_user_model):
    # Cria profissional (user) e força login
    pro = django_user_model.objects.create_user(email='p@example.com', password='x', first_name='P', last_name='X')
    client.force_login(pro)
    c = Client.objects.create(professional=pro, first_name='C', last_name='L')
    appt = Appointment.objects.create(
        professional=pro,
        client=c,
        title='Consulta',
        start_at=timezone.now() + timezone.timedelta(minutes=10),
        end_at=timezone.now() + timezone.timedelta(minutes=40),
        status=Appointment.Status.SCHEDULED,
    )
    r = client.post(f'/agenda/appointments/{appt.id}/finalize/')
    assert r.status_code == 422
    assert r.json().get('code') == 'too_early'


@pytest.mark.django_db
def test_finalize_in_progress_shortens_end(client, django_user_model):
    pro = django_user_model.objects.create_user(email='p2@example.com', password='x', first_name='P2', last_name='X2')
    client.force_login(pro)
    now = timezone.now()
    c = Client.objects.create(professional=pro, first_name='C2', last_name='L2')
    appt = Appointment.objects.create(
        professional=pro,
        client=c,
        title='Sessão',
        start_at=now - timezone.timedelta(minutes=5),
        end_at=now + timezone.timedelta(minutes=25),
        status=Appointment.Status.SCHEDULED,
    )
    orig_end = appt.end_at
    r = client.post(f'/agenda/appointments/{appt.id}/finalize/')
    assert r.status_code == 200
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.PENDING
    assert appt.finalized_at is not None
    # Deve ter encurtado (end_at < orig_end)
    assert appt.end_at < orig_end


@pytest.mark.django_db
def test_finalize_after_past_keeps_end(client, django_user_model):
    pro = django_user_model.objects.create_user(email='p3@example.com', password='x', first_name='P3', last_name='X3')
    client.force_login(pro)
    now = timezone.now()
    c = Client.objects.create(professional=pro, first_name='C3', last_name='L3')
    appt = Appointment.objects.create(
        professional=pro,
        client=c,
        title='Revisão',
        start_at=now - timezone.timedelta(hours=2),
        end_at=now - timezone.timedelta(hours=1, minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    orig_end = appt.end_at
    r = client.post(f'/agenda/appointments/{appt.id}/finalize/')
    assert r.status_code == 200
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.PENDING
    assert appt.finalized_at is not None
    # Não deve encurtar (mantém fim planejado porque já passou)
    assert appt.end_at == orig_end


@pytest.mark.django_db
def test_done_moves_pending_to_done(client, django_user_model):
    pro = django_user_model.objects.create_user(email='p4@example.com', password='x', first_name='P4', last_name='X4')
    client.force_login(pro)
    now = timezone.now()
    c = Client.objects.create(professional=pro, first_name='C4', last_name='L4')
    appt = Appointment.objects.create(
        professional=pro,
        client=c,
        title='Sessão',
        start_at=now - timezone.timedelta(minutes=30),
        end_at=now - timezone.timedelta(minutes=10),
        status=Appointment.Status.PENDING,
        finalized_at=now - timezone.timedelta(minutes=10),
    )

    r = client.post(f'/agenda/appointments/{appt.id}/done/')
    assert r.status_code == 200
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.DONE


@pytest.mark.django_db
def test_done_requires_pending_first(client, django_user_model):
    pro = django_user_model.objects.create_user(email='p5@example.com', password='x', first_name='P5', last_name='X5')
    client.force_login(pro)
    now = timezone.now()
    c = Client.objects.create(professional=pro, first_name='C5', last_name='L5')
    appt = Appointment.objects.create(
        professional=pro,
        client=c,
        title='Sessão',
        start_at=now - timezone.timedelta(minutes=5),
        end_at=now + timezone.timedelta(minutes=25),
        status=Appointment.Status.SCHEDULED,
    )

    r = client.post(f'/agenda/appointments/{appt.id}/done/')
    assert r.status_code == 409
    assert r.json().get('code') == 'must_finalize_first'
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.SCHEDULED
