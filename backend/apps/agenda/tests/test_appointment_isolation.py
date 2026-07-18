import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.agenda.models import Appointment
from apps.clients.models import Client
from apps.register.models import Professional


pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return Professional.objects.create_user(
        email="agenda-owner@example.com",
        password="secret123",
        first_name="Owner",
        last_name="Agenda",
    )


@pytest.fixture
def other_professional():
    return Professional.objects.create_user(
        email="agenda-other@example.com",
        password="secret123",
        first_name="Other",
        last_name="Agenda",
    )


@pytest.fixture
def owner_client(owner):
    return Client.objects.create(
        professional=owner,
        first_name="Owner",
        last_name="Client",
        phone="11972000001",
    )


@pytest.fixture
def other_client(other_professional):
    return Client.objects.create(
        professional=other_professional,
        first_name="Other",
        last_name="Client",
        phone="11972000002",
    )


@pytest.fixture
def owner_appointment(owner, owner_client):
    start = timezone.now() + timezone.timedelta(days=1)
    return Appointment.objects.create(
        professional=owner,
        client=owner_client,
        title="Owner Appointment",
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=start,
        end_at=start + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )


@pytest.fixture
def other_appointment(other_professional, other_client):
    start = timezone.now() + timezone.timedelta(days=1, hours=1)
    return Appointment.objects.create(
        professional=other_professional,
        client=other_client,
        title="Other Appointment",
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=start,
        end_at=start + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )


@pytest.fixture
def api_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def test_professional_lists_only_own_appointments(
    api_client,
    owner_appointment,
    other_appointment,
):
    response = api_client.get("/agenda/appointments/")

    assert response.status_code == 200, response.content
    ids = {item["id"] for item in response.json()}
    assert owner_appointment.id in ids
    assert other_appointment.id not in ids


def test_professional_cannot_read_other_professional_appointment(
    api_client,
    other_appointment,
):
    response = api_client.get(f"/agenda/appointments/{other_appointment.id}/")

    assert response.status_code == 404


def test_professional_cannot_update_other_professional_appointment(
    api_client,
    other_appointment,
):
    response = api_client.patch(
        f"/agenda/appointments/{other_appointment.id}/",
        {"title": "Changed"},
        format="json",
    )

    assert response.status_code == 404
    other_appointment.refresh_from_db()
    assert other_appointment.title == "Other Appointment"


def test_professional_cannot_create_appointment_for_other_professional_client(
    api_client,
    other_client,
):
    start = timezone.now() + timezone.timedelta(days=2)

    response = api_client.post(
        "/agenda/appointments/",
        {
            "client": other_client.id,
            "title": "Cross Owner Appointment",
            "visit_type": Appointment.VisitType.CONSULTA,
            "start_at": start.isoformat(),
            "end_at": (start + timezone.timedelta(minutes=30)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400, response.content
    assert "client" in response.json()
    assert not Appointment.objects.filter(title="Cross Owner Appointment").exists()