import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.agenda import Appointment


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def professional(db):
    return Professional.objects.create_user( # type: ignore
        email='agendaapi@example.com', password='secret123', first_name='Agenda', last_name='API'
    )


@pytest.fixture
def tenant(db, professional):
    t = Tenant.objects.create(
        name='Consultório Podologia',
        slug='consultorio-podologia',
        ecosystem='clinic',
        is_active=True,
        capabilities={'clinic': True, 'podologia': True},
    )
    TenantMembership.objects.create(
        tenant=t,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return t


@pytest.fixture
def auth_client(api_client, professional, tenant):
    # Obtem token JWT e seta Authorization header
    r = api_client.post('/token/', {'email': professional.email, 'password': 'secret123'}, format='json')
    access = r.json()['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return api_client


@pytest.fixture
def client_obj(db, professional, tenant):
    return Client.objects.create(
        tenant=tenant,
        first_name='Cliente',
        last_name='API',
        phone='11988887777'
    )


@pytest.mark.django_db
def test_cannot_create_past_appointment(auth_client, client_obj):
    past_start = timezone.now() - timezone.timedelta(hours=2)
    payload = {
        'client': client_obj.id,
        'title': 'Consulta Passada',
        'visit_type': 'consulta',
        'start_at': past_start.isoformat(),
        'end_at': (past_start + timezone.timedelta(hours=1)).isoformat(),
    }
    r = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r.status_code in (400, 422), r.content
    data = r.json()
    # Converte para lista/str conforme formato DRF: {field: ["msg"]} ou {field: "msg"}
    start_errors = data.get('start_at')
    if isinstance(start_errors, list):
        joined = ' '.join(start_errors)
    else:
        joined = str(start_errors)
    assert 'passado' in joined.lower()


@pytest.mark.django_db
def test_create_future_and_conflict(auth_client, client_obj):
    base = (timezone.now() + timezone.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    payload = {
        'client': client_obj.id,
        'title': 'Primeira',
        'visit_type': 'consulta',
        'start_at': base.isoformat(),
        'end_at': (base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r1 = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r1.status_code == 201, r1.content

    # Tentar conflito parcial sobrepondo dentro do período existente
    conflict_payload = {
        'client': client_obj.id,
        'title': 'Conflito',
        'visit_type': 'consulta',
        'start_at': (base + timezone.timedelta(minutes=15)).isoformat(),
        'end_at': (base + timezone.timedelta(minutes=45)).isoformat(),
    }
    r2 = auth_client.post('/agenda/appointments/', conflict_payload, format='json')
    # Conflito gera 400 ValidationError
    assert r2.status_code in (400, 409), r2.content
    body = r2.json()
    # Mensagem geral ou detail
    combined = ' '.join(str(v) for v in body.values())
    assert 'conflit' in combined.lower()


@pytest.mark.django_db
def test_multiple_same_day_allowed_if_no_overlap(auth_client, client_obj):
    base = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
    if base <= timezone.now():
        base = base + timezone.timedelta(days=1)

    first_payload = {
        'client': client_obj.id,
        'title': 'Sessão manhã',
        'visit_type': 'consulta',
        'start_at': base.isoformat(),
        'end_at': (base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r1 = auth_client.post('/agenda/appointments/', first_payload, format='json')
    assert r1.status_code == 201, r1.content

    second_start = base.replace(hour=10)
    second_payload = {
        'client': client_obj.id,
        'title': 'Sessão tarde',
        'visit_type': 'retorno',
        'start_at': second_start.isoformat(),
        'end_at': (second_start + timezone.timedelta(minutes=30)).isoformat(),
    }
    r2 = auth_client.post('/agenda/appointments/', second_payload, format='json')
    assert r2.status_code == 201, r2.content


@pytest.mark.django_db
def test_block_new_when_client_has_pending_past(auth_client, client_obj, professional, tenant):
    # Cria um agendamento passado com status scheduled (pendente)
    base = (timezone.now() - timezone.timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    past_payload = {
        'client': client_obj.id,
        'title': 'Pendente Antigo',
        'visit_type': 'consulta',
        'start_at': base.isoformat(),
        'end_at': (base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r1 = auth_client.post('/agenda/appointments/', past_payload, format='json')
    # Dependendo das regras existentes, criar no passado pode falhar via API. Então criamos diretamente via ORM.
    if r1.status_code not in (200, 201):
        from apps.clinic.models.agenda import Appointment
        Appointment.objects.create(
            tenant=tenant,
            professional=professional,
            client=client_obj,
            title='Pendente Antigo',
            visit_type='consulta',
            start_at=base,
            end_at=base + timezone.timedelta(minutes=30),
            status='scheduled',
        )

    # Agora tente criar um novo no futuro: deve ser bloqueado por pendência
    future_base = (timezone.now() + timezone.timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    new_payload = {
        'client': client_obj.id,
        'title': 'Nova Consulta',
        'visit_type': 'consulta',
        'start_at': future_base.isoformat(),
        'end_at': (future_base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r2 = auth_client.post('/agenda/appointments/', new_payload, format='json')
    assert r2.status_code in (400, 422), r2.content
    body = r2.json()
    text = ' '.join(str(v) for v in body.values())
    assert 'pendente' in text.lower()


@pytest.mark.django_db
def test_block_new_when_client_has_persisted_pending(auth_client, client_obj, professional, tenant):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() - timezone.timedelta(hours=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Pendente Persistido',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.PENDING,
    )

    future_base = (timezone.now() + timezone.timedelta(hours=2)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    payload = {
        'client': client_obj.id,
        'title': 'Nova Consulta',
        'visit_type': 'consulta',
        'start_at': future_base.isoformat(),
        'end_at': (future_base + timezone.timedelta(minutes=30)).isoformat(),
    }

    r = auth_client.post('/agenda/appointments/', payload, format='json')

    assert r.status_code in (400, 422), r.content
    body = r.json()
    text = ' '.join(str(v) for v in body.values())
    assert 'pendente' in text.lower()


@pytest.mark.django_db
def test_list_honors_ordering_and_limit(auth_client, client_obj, professional, tenant):
    base = (timezone.now() + timezone.timedelta(hours=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    first = Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Primeiro',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    second = Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Segundo',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base + timezone.timedelta(hours=1),
        end_at=base + timezone.timedelta(hours=1, minutes=30),
        status=Appointment.Status.SCHEDULED,
    )

    response = auth_client.get('/agenda/appointments/?ordering=-end_at&limit=1')

    assert response.status_code == 200, response.content
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['id'] == second.id
    assert data[0]['id'] != first.id


@pytest.mark.django_db
def test_pending_does_not_create_temporal_conflict(auth_client, client_obj, professional, tenant):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() + timezone.timedelta(hours=2)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Pendente sobreposto',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.PENDING,
    )

    other_client = Client.objects.create(
        tenant=tenant,
        first_name='Outro',
        last_name='Cliente',
        phone='11988887766',
    )
    assert other_client.pk is not None

    payload = {
        'client': other_client.pk,
        'title': 'Novo agendamento válido',
        'visit_type': 'consulta',
        'start_at': (base + timezone.timedelta(minutes=10)).isoformat(),
        'end_at': (base + timezone.timedelta(minutes=40)).isoformat(),
    }

    r = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r.status_code == 201, r.content


@pytest.mark.django_db
def test_status_filter_accepts_pending_value(auth_client, client_obj, professional, tenant):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() + timezone.timedelta(hours=2)).replace(
        second=0,
        microsecond=0,
    )

    Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Compromisso pendente',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.PENDING,
    )
    Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Compromisso agendado',
        visit_type=Appointment.VisitType.RETORNO,
        start_at=base + timezone.timedelta(hours=1),
        end_at=base + timezone.timedelta(hours=1, minutes=30),
        status=Appointment.Status.SCHEDULED,
    )

    r = auth_client.get('/agenda/appointments/?status=pending')

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]['status'] == Appointment.Status.PENDING


@pytest.mark.django_db
def test_list_promotes_overdue_scheduled_to_pending(auth_client, client_obj, professional, tenant):
    from apps.clinic.models.agenda import Appointment

    start = timezone.now() - timezone.timedelta(hours=2)
    appt = Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Expirado',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=start,
        end_at=start + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )

    r = auth_client.get(
        '/agenda/appointments/',
        {'status': Appointment.Status.PENDING},
    )

    assert r.status_code == 200, r.content
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.PENDING
    assert appt.pk is not None
    ids = [item['id'] for item in r.json()]
    assert appt.pk in ids


@pytest.mark.django_db
def test_list_marks_overdue_odonto_appointment_as_done(auth_client, client_obj, professional, tenant):
    tenant.capabilities = {'clinic': True, 'odonto': True}
    tenant.save(update_fields=['capabilities'])
    start = timezone.now() - timezone.timedelta(hours=2)
    appt = Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Odonto expirado',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=start,
        end_at=start + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )

    r = auth_client.get('/agenda/appointments/', {'status': Appointment.Status.DONE})

    assert r.status_code == 200, r.content
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.DONE
    assert appt.id in [item['id'] for item in r.json()]


@pytest.mark.django_db
def test_pending_then_cancel_allows_new(auth_client, professional, client_obj, tenant):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() - timezone.timedelta(hours=5)).replace(
        second=0,
        microsecond=0,
    )
    past = Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Pendente',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    assert past.pk is not None

    future_base = (timezone.now() + timezone.timedelta(hours=2)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    payload = {
        'client': client_obj.id,
        'title': 'Nova Consulta',
        'visit_type': 'consulta',
        'start_at': future_base.isoformat(),
        'end_at': (future_base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r_block = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r_block.status_code in (400, 422), r_block.content

    r_cancel = auth_client.post(f'/agenda/appointments/{past.pk}/cancel/')
    assert r_cancel.status_code == 200
    past.refresh_from_db()
    assert past.status == Appointment.Status.CANCELED

    r_ok = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r_ok.status_code == 201, r_ok.content


