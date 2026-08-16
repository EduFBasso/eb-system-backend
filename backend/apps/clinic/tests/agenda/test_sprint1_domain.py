import pytest
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.test import APIClient

from apps.clinic.models.agenda import Appointment, Charge, ClinicalRecord, Encounter
from apps.clinic.models.clients import Client
from apps.clinic.models.inventory import Product, Service
from apps.authentication.models import Professional, Tenant, TenantMembership


pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    pro = Professional.objects.create_user(
        email="sprint1@example.com",
        password="secret123",
        first_name="Sprint",
        last_name="One",
    )
    pro.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Sprint1', slug='tenant-sprint1')
    TenantMembership.objects.create(
        tenant=tenant, professional=pro,
        role=TenantMembership.Role.OWNER, is_active=True,
    )
    return pro


@pytest.fixture
def other_professional():
    pro = Professional.objects.create_user(
        email="other-sprint1@example.com",
        password="secret123",
        first_name="Other",
        last_name="Professional",
    )
    pro.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Sprint1 Other', slug='tenant-sprint1-other')
    TenantMembership.objects.create(
        tenant=tenant, professional=pro,
        role=TenantMembership.Role.OWNER, is_active=True,
    )
    return pro


@pytest.fixture
def auth_client(professional):
    client = APIClient()
    client.force_authenticate(user=professional)
    return client


@pytest.fixture
def staff_professional():
    pro = Professional.objects.create_user(
        email="staff-sprint1@example.com",
        password="secret123",
        first_name="Staff",
        last_name="Reviewer",
    )
    pro.is_staff = True
    pro.save(update_fields=["is_staff"])
    pro.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Staff Sprint1', slug='tenant-staff-sprint1')
    TenantMembership.objects.create(
        tenant=tenant, professional=pro,
        role=TenantMembership.Role.OWNER, is_active=True,
    )
    return pro


@pytest.fixture
def staff_client(staff_professional):
    client = APIClient()
    client.force_authenticate(user=staff_professional)
    return client


@pytest.fixture
def client_obj(professional):
    return Client.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        first_name="Cliente",
        last_name="Sprint",
        phone="11999998888",
    )


@pytest.fixture
def other_client(other_professional):
    return Client.objects.create(
        tenant=other_professional.tenant_memberships.first().tenant,
        first_name="Outro",
        last_name="Cliente",
        phone="11999997777",
    )


@pytest.fixture
def service(professional):
    return Service.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        name="Avaliação biomânica",
        base_price="120.00",
    )


@pytest.fixture
def product(professional):
    return Product.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        name="Palmilha",
        price="80.00",
        cost="35.00",
    )


def make_future_appointment(professional, client_obj, hours_ahead: int = 2):
    start_at = (timezone.now() + timezone.timedelta(hours=hours_ahead)).replace(
        second=0,
        microsecond=0,
    )
    return Appointment.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        title="Consulta",
        visit_type=Appointment.VisitType.CONSULTA,
        start_at=start_at,
        end_at=start_at + timezone.timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )


def test_create_independent_encounter(auth_client, client_obj):
    response = auth_client.post(
        "/agenda/encounters/",
        {
            "client": client_obj.id,
            "chief_complaint": "Dor plantar há 2 semanas",
            "assessment": "Paciente refere piora ao caminhar.",
            "plan": "Realizar avaliação e orientar descarga.",
            "notes": "Chegou sem agendamento.",
            "status": "open",
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["appointment"] is None
    assert data["status"] == "open"


def test_only_one_open_encounter_per_client(auth_client, client_obj, professional):
    Encounter.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        chief_complaint="Dor",
        status=Encounter.Status.OPEN,
    )

    response = auth_client.post(
        "/agenda/encounters/",
        {
            "client": client_obj.id,
            "chief_complaint": "Nova avaliação",
            "status": "open",
        },
        format="json",
    )

    assert response.status_code == 400, response.content
    assert "sessão" in str(response.json()).lower() or "atendimento" in str(response.json()).lower()

def test_clinical_record_requires_matching_encounter(auth_client, client_obj, other_client, other_professional):
    encounter = Encounter.objects.create(
        tenant=other_professional.tenant_memberships.first().tenant,
        professional=other_professional,
        client=other_client,
        chief_complaint="Outro caso",
        status=Encounter.Status.OPEN,
    )

    response = auth_client.post(
        "/agenda/clinical-records/",
        {
            "client": client_obj.id,
            "encounter": encounter.id,
            "record_type": "evolution",
            "title": "Primeira evolução",
            "content": "Paciente evolui bem.",
        },
        format="json",
    )

    assert response.status_code == 400, response.content
    assert "mesmo cliente" in str(response.json()).lower() or "mesmo profissional" in str(response.json()).lower()


def test_create_charge_with_items_recalculates_total(auth_client, client_obj, service, product):
    response = auth_client.post(
        "/agenda/charges/",
        {
            "client": client_obj.id,
            "charge_type": "charge",
            "status": "draft",
            "title": "Cobrança do atendimento",
            "recipient_name": "Cliente Sprint",
            "recipient_phone": "11999998888",
            "items": [
                {
                    "item_type": "service",
                    "service": service.id,
                    "quantity": "1.00",
                    "unit_price": "120.00",
                    "sort_order": 0,
                },
                {
                    "item_type": "product",
                    "product": product.id,
                    "quantity": "2.00",
                    "unit_price": "80.00",
                    "sort_order": 1,
                },
                {
                    "item_type": "custom",
                    "description": "Deslocamento",
                    "quantity": "1.00",
                    "unit_price": "20.00",
                    "sort_order": 2,
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["total_amount"] == "300.00"
    assert len(data["items"]) == 3


def test_charge_mark_paid_sets_paid_at(auth_client, client_obj, professional):
    charge = Charge.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        charge_type=Charge.ChargeType.CHARGE,
        status=Charge.Status.DRAFT,
        title="Cobrança simples",
    )
    charge.items.create(
        item_type="custom",
        description="Consulta",
        quantity="1.00",
        unit_price="100.00",
    )

    response = auth_client.post(f"/agenda/charges/{charge.id}/mark-paid/", format="json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == "paid"
    assert data["paid_at"] is not None


def test_paid_charge_keeps_status_when_items_are_updated(auth_client, client_obj, professional):
    charge = Charge.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        charge_type=Charge.ChargeType.CHARGE,
        status=Charge.Status.PAID,
        title="Cobrança paga",
    )
    original_paid_at = charge.paid_at
    charge.items.create(
        item_type="custom",
        description="Consulta",
        quantity="1.00",
        unit_price="100.00",
        paid=False,
        paid_at=None,
    )

    response = auth_client.patch(
        f"/agenda/charges/{charge.id}/",
        {
            "client": client_obj.id,
            "charge_type": "charge",
            "title": "Cobrança paga",
            "items": [
                {
                    "item_type": "custom",
                    "description": "Consulta atualizada",
                    "quantity": "1.00",
                    "unit_price": "120.00",
                    "paid": False,
                    "paid_at": None,
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == "paid"
    returned_paid_at = parse_datetime(data["paid_at"])
    assert returned_paid_at == original_paid_at


def test_mark_sent_does_not_downgrade_paid_charge(auth_client, client_obj, professional):
    charge = Charge.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        charge_type=Charge.ChargeType.CHARGE,
        status=Charge.Status.PAID,
        title="Cobrança já paga",
    )

    response = auth_client.post(f"/agenda/charges/{charge.id}/mark-sent/", format="json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == "paid"
    assert data["paid_at"] is not None
    assert data["shared_at"] is not None


def test_charge_cancel_marks_canceled(auth_client, client_obj, professional):
    charge = Charge.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        charge_type=Charge.ChargeType.CHARGE,
        status=Charge.Status.DRAFT,
        title="Cobrança em aberto",
    )

    response = auth_client.post(f"/agenda/charges/{charge.id}/cancel/", format="json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == "canceled"
    assert data["paid_at"] is None


def test_charge_cancel_blocks_paid_charge(auth_client, client_obj, professional):
    charge = Charge.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        charge_type=Charge.ChargeType.CHARGE,
        status=Charge.Status.PAID,
        title="Cobrança quitada",
    )

    response = auth_client.post(f"/agenda/charges/{charge.id}/cancel/", format="json")

    assert response.status_code == 400, response.content
    assert "não pode ser cancelada" in str(response.json()).lower()


def test_encounter_close_sets_ended_at(auth_client, client_obj, professional):
    encounter = Encounter.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        chief_complaint="Dor",
        status=Encounter.Status.OPEN,
    )

    response = auth_client.post(f"/agenda/encounters/{encounter.id}/close/", format="json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == "closed"
    assert data["ended_at"] is not None


def test_encounter_cancel_sets_canceled(auth_client, client_obj, professional):
    encounter = Encounter.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        chief_complaint="Retorno",
        status=Encounter.Status.OPEN,
    )

    response = auth_client.post(f"/agenda/encounters/{encounter.id}/cancel/", format="json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == "canceled"
    assert data["ended_at"] is not None


def test_clinical_record_delete_is_blocked(auth_client, client_obj, professional):
    record = ClinicalRecord.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        professional=professional,
        client=client_obj,
        record_type=ClinicalRecord.RecordType.NOTE,
        title="Nota",
        content="Histórico preservado.",
        recorded_at=timezone.now(),
    )

    response = auth_client.delete(f"/agenda/clinical-records/{record.id}/")

    assert response.status_code == 405