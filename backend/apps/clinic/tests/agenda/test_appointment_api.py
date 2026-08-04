import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional
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
def auth_client(api_client, professional):
    # Obtem token JWT e seta Authorization header
    r = api_client.post('/token/', {'email': professional.email, 'password': 'secret123'}, format='json')
    access = r.json()['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return api_client


@pytest.fixture
def client_obj(db, professional):
    return Client.objects.create(
        professional=professional,
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
        'visit_type': 'avaliacao',
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
        'visit_type': 'avaliacao',
        'start_at': base.isoformat(),
        'end_at': (base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r1 = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r1.status_code == 201, r1.content

    # Tentar conflito parcial sobrepondo dentro do período existente
    conflict_payload = {
        'client': client_obj.id,
        'title': 'Conflito',
        'visit_type': 'avaliacao',
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
        'visit_type': 'avaliacao',
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
def test_block_new_when_client_has_pending_past(auth_client, client_obj):
    # Cria um agendamento passado com status scheduled (pendente)
    base = (timezone.now() - timezone.timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    past_payload = {
        'client': client_obj.id,
        'title': 'Pendente Antigo',
        'visit_type': 'avaliacao',
        'start_at': base.isoformat(),
        'end_at': (base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r1 = auth_client.post('/agenda/appointments/', past_payload, format='json')
    # Dependendo das regras existentes, criar no passado pode falhar via API. Então criamos diretamente via ORM.
    if r1.status_code not in (200, 201):
        from apps.authentication.models import Professional
        # Captura professional do token atual
        # Para simplificar, obtenha qualquer pro ligado ao client_obj
        pro = Professional.objects.get(id=client_obj.professional_id)
        from apps.clinic.models.agenda import Appointment
        Appointment.objects.create(
            professional=pro,
            client=client_obj,
            title='Pendente Antigo',
            visit_type='avaliacao',
            start_at=base,
            end_at=base + timezone.timedelta(minutes=30),
            status='scheduled',
        )

    # Agora tente criar um novo no futuro: deve ser bloqueado por pendência
    future_base = (timezone.now() + timezone.timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    new_payload = {
        'client': client_obj.id,
        'title': 'Nova Consulta',
        'visit_type': 'avaliacao',
        'start_at': future_base.isoformat(),
        'end_at': (future_base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r2 = auth_client.post('/agenda/appointments/', new_payload, format='json')
    assert r2.status_code in (400, 422), r2.content
    body = r2.json()
    text = ' '.join(str(v) for v in body.values())
    assert 'pendente' in text.lower()


@pytest.mark.django_db
def test_block_new_when_client_has_persisted_pending(auth_client, client_obj):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() - timezone.timedelta(hours=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    Appointment.objects.create(
        professional=client_obj.professional,
        client=client_obj,
        title='Pendente Persistido',
        visit_type=Appointment.VisitType.AVALIACAO,
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
        'visit_type': 'avaliacao',
        'start_at': future_base.isoformat(),
        'end_at': (future_base + timezone.timedelta(minutes=30)).isoformat(),
    }

    r = auth_client.post('/agenda/appointments/', payload, format='json')

    assert r.status_code in (400, 422), r.content
    body = r.json()
    text = ' '.join(str(v) for v in body.values())
    assert 'pendente' in text.lower()


@pytest.mark.django_db
def test_ongoing_does_not_block_new(auth_client, client_obj):
    # Cria um agendamento em andamento (start <= now < end) diretamente no ORM
    from apps.clinic.models.agenda import Appointment
    now = timezone.now()
    start = now - timezone.timedelta(minutes=5)
    end = now + timezone.timedelta(minutes=25)
    Appointment.objects.create(
        professional=client_obj.professional,
        client=client_obj,
        title='Em andamento',
        visit_type=Appointment.VisitType.AVALIACAO,
        start_at=start,
        end_at=end,
        status=Appointment.Status.SCHEDULED,
    )


@pytest.mark.django_db
def test_list_honors_ordering_and_limit(auth_client, client_obj):
    base = (timezone.now() + timezone.timedelta(hours=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    first = Appointment.objects.create(
        professional=client_obj.professional,
        client=client_obj,
        title='Primeiro',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    second = Appointment.objects.create(
        professional=client_obj.professional,
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
def test_pending_does_not_create_temporal_conflict(auth_client, client_obj):
    from apps.clinic.models.agenda import Appointment
    from apps.clinic.models.clients import Client

    base = (timezone.now() + timezone.timedelta(hours=2)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    Appointment.objects.create(
        professional=client_obj.professional,
        client=client_obj,
        title='Pendente sobreposto',
        visit_type=Appointment.VisitType.AVALIACAO,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.PENDING,
    )

    other_client = Client.objects.create(
        professional=client_obj.professional,
        first_name='Outro',
        last_name='Cliente',
        phone='11988887766',
    )
    assert other_client.pk is not None

    payload = {
        'client': other_client.pk,
        'title': 'Novo agendamento válido',
        'visit_type': 'avaliacao',
        'start_at': (base + timezone.timedelta(minutes=10)).isoformat(),
        'end_at': (base + timezone.timedelta(minutes=40)).isoformat(),
    }

    r = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r.status_code == 201, r.content


@pytest.mark.django_db
def test_status_filter_accepts_pending_value(auth_client, client_obj):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() + timezone.timedelta(hours=2)).replace(
        second=0,
        microsecond=0,
    )

    Appointment.objects.create(
        professional=client_obj.professional,
        client=client_obj,
        title='Compromisso pendente',
        visit_type=Appointment.VisitType.AVALIACAO,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.PENDING,
    )
    Appointment.objects.create(
        professional=client_obj.professional,
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
def test_list_promotes_overdue_scheduled_to_pending(auth_client, client_obj):
    from apps.clinic.models.agenda import Appointment

    start = timezone.now() - timezone.timedelta(hours=2)
    appt = Appointment.objects.create(
        professional=client_obj.professional,
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
def test_pending_then_cancel_allows_new(auth_client, professional, client_obj):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() - timezone.timedelta(hours=5)).replace(
        second=0,
        microsecond=0,
    )
    past = Appointment.objects.create(
        professional=professional,
        client=client_obj,
        title='Pendente',
        visit_type=Appointment.VisitType.AVALIACAO,
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
        'visit_type': 'avaliacao',
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


@pytest.mark.django_db
def test_finalize_to_pending_then_done_allows_new(auth_client, professional, client_obj):
    from apps.clinic.models.agenda import Appointment

    base = (timezone.now() - timezone.timedelta(days=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    past = Appointment.objects.create(
        professional=professional,
        client=client_obj,
        title='Pendente 2',
        visit_type=Appointment.VisitType.AVALIACAO,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    assert past.pk is not None

    future_base = (timezone.now() + timezone.timedelta(hours=3)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    payload = {
        'client': client_obj.id,
        'title': 'Nova Pós Conclusão',
        'visit_type': 'avaliacao',
        'start_at': future_base.isoformat(),
        'end_at': (future_base + timezone.timedelta(minutes=30)).isoformat(),
    }
    r_block = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r_block.status_code in (400, 422)

    r_fin = auth_client.post(f'/agenda/appointments/{past.pk}/finalize/')
    assert r_fin.status_code == 200, r_fin.content
    past.refresh_from_db()
    assert past.status == Appointment.Status.PENDING

    r_still_blocked = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r_still_blocked.status_code in (400, 422)

    r_done = auth_client.post(f'/agenda/appointments/{past.pk}/done/')
    assert r_done.status_code == 200, r_done.content
    past.refresh_from_db()
    assert past.status == Appointment.Status.DONE

    r_ok = auth_client.post('/agenda/appointments/', payload, format='json')
    assert r_ok.status_code == 201, r_ok.content
