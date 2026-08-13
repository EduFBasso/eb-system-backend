import pytest
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.clinic.models.agenda import Appointment
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional, Tenant, TenantMembership


@pytest.fixture
def professional(db):
    pro = Professional.objects.create_user(
        email="pro1@example.com", password="x", first_name="Pro", last_name="One"
    )
    pro.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Pro1', slug='tenant-pro1')
    TenantMembership.objects.create(
        tenant=tenant, professional=pro,
        role=TenantMembership.Role.OWNER, is_active=True,
    )
    return pro


@pytest.fixture
def client(db, professional):
    return Client.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        first_name="Cliente",
        last_name="Teste",
        phone="19999999999",
    )


def test_end_before_start_validation(db, professional, client):
    start = timezone.now()
    ap = Appointment(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="Teste",
        start_at=start,
        end_at=start,  # igual -> inválido
    )
    with pytest.raises(ValidationError):
        ap.full_clean()


def test_overlaps_true(db, professional, client):
    base = timezone.now().replace(minute=0, second=0, microsecond=0)
    a1 = Appointment.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="A1",
        start_at=base,
        end_at=base + timezone.timedelta(hours=1),
    )
    a2 = Appointment(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="A2",
        start_at=base + timezone.timedelta(minutes=30),
        end_at=base + timezone.timedelta(hours=1, minutes=30),
    )
    assert a2.overlaps() is True


def test_overlaps_false(db, professional, client):
    base = timezone.now().replace(minute=0, second=0, microsecond=0)
    Appointment.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="A1",
        start_at=base,
        end_at=base + timezone.timedelta(hours=1),
    )
    a3 = Appointment(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="A3",
        start_at=base + timezone.timedelta(hours=2),
        end_at=base + timezone.timedelta(hours=3),
    )
    assert a3.overlaps() is False


def test_pending_status_persists(db, professional, client):
    base = (timezone.now() + timezone.timedelta(hours=1)).replace(
        second=0,
        microsecond=0,
    )
    appt = Appointment.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title='Pendente persistido',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(minutes=30),
        status=Appointment.Status.PENDING,
    )

    appt.refresh_from_db()
    assert appt.status == Appointment.Status.PENDING