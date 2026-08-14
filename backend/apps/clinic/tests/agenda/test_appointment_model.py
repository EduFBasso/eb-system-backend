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


def test_appointment_overlap_same_professional(db, professional, client):
    base = timezone.now().replace(minute=0, second=0, microsecond=0)
    a1 = Appointment.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="A1",
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(hours=1),
    )
    a2 = Appointment(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="A2",
        visit_type=Appointment.VisitType.CONSULTA,
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
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(hours=1),
    )
    a3 = Appointment(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client,
        title="A3",
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base + timezone.timedelta(hours=2),
        end_at=base + timezone.timedelta(hours=3),
    )
    assert a3.overlaps() is False


def test_appointments_same_time_different_tenants_allowed(db):
    professional = Professional.objects.create_user(
        email='shared.pro@example.com',
        password='x',
        first_name='Shared',
        last_name='Pro',
    )
    professional.tenant_memberships.all().delete()

    tenant_a = Tenant.objects.create(name='Tenant A', slug='tenant-a')
    tenant_b = Tenant.objects.create(name='Tenant B', slug='tenant-b')

    TenantMembership.objects.create(
        tenant=tenant_a,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    TenantMembership.objects.create(
        tenant=tenant_b,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )

    client_a = Client.objects.create(
        tenant=tenant_a,
        first_name='Cliente',
        last_name='A',
        phone='19999999991',
    )
    client_b = Client.objects.create(
        tenant=tenant_b,
        first_name='Cliente',
        last_name='B',
        phone='19999999992',
    )

    base = timezone.now().replace(minute=0, second=0, microsecond=0)

    Appointment.objects.create(
        tenant=tenant_a,
        professional=professional,
        client=client_a,
        title='A1',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(hours=1),
    )

    appointment_other_tenant = Appointment(
        tenant=tenant_b,
        professional=professional,
        client=client_b,
        title='B1',
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=base,
        end_at=base + timezone.timedelta(hours=1),
    )

    assert appointment_other_tenant.overlaps() is False


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