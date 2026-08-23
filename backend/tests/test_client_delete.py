from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.clinic.models.agenda import Appointment, Charge, ClinicalRecord, Encounter
from apps.clinic.models.anamnesis import AnamneseBase, AnamnesePodologia
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional
from apps.authentication.models import Tenant, TenantMembership


pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    professional = Professional.objects.create_user(
        email='delete-owner@example.com',
        password='secret123',
        first_name='Owner',
        last_name='Tester',
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Delete', slug='tenant-delete')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def auth_client(professional):
    client = APIClient()
    token = AccessToken.for_user(professional)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.fixture
def client_obj(professional):
    return Client.objects.create(
        tenant=professional.tenant_memberships.first().tenant,
        first_name='Cliente',
        last_name='Excluir',
        phone='11999999991',
    )


def test_delete_client_cascades_related_records(auth_client, professional, client_obj):
    tenant = professional.tenant_memberships.first().tenant
    start_at = timezone.now() + timedelta(hours=1)
    appointment = Appointment.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        title='Consulta ativa',
        start_at=start_at,
        end_at=start_at + timedelta(hours=1),
    )
    encounter = Encounter.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        appointment=appointment,
        notes='Atendimento em aberto',
    )
    ClinicalRecord.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        encounter=encounter,
        content='Registro clínico',
    )
    Charge.objects.create(
        tenant=tenant,
        professional=professional,
        client=client_obj,
        encounter=encounter,
        appointment=appointment,
        title='Cobrança teste',
    )
    anamnesis = AnamneseBase.objects.create(
        client=client_obj,
        tenant=tenant,
        professional=professional,
        takes_medication='Sim',
    )
    AnamnesePodologia.objects.create(
        anamnese_base=anamnesis,
        professional=professional,
        footwear_used='Tênis',
    )

    response = auth_client.delete(f'/register/clients/{client_obj.id}/')

    assert response.status_code == 204, response.content
    assert not Client.objects.filter(pk=client_obj.id).exists()
    assert not Appointment.objects.filter(client_id=client_obj.id).exists()
    assert not Encounter.objects.filter(client_id=client_obj.id).exists()
    assert not ClinicalRecord.objects.filter(client_id=client_obj.id).exists()
    assert not Charge.objects.filter(client_id=client_obj.id).exists()
    assert not AnamneseBase.objects.filter(client_id=client_obj.id).exists()
    assert not AnamnesePodologia.objects.filter(
        anamnese_base_id=anamnesis.id,
    ).exists()


def test_clients_basic_detail_is_read_only(auth_client, client_obj):
    response = auth_client.delete(f'/register/clients-basic/{client_obj.id}/')

    assert response.status_code == 405, response.content
    assert Client.objects.filter(pk=client_obj.id).exists()