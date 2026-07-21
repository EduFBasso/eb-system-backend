from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.anamnesis.models import AnamnesisField, AnamnesisResponse
from apps.clients.models import Client
from apps.register.models import Professional
from apps.tenancy.models import TenantMembership


pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    return Professional.objects.create_user(
        email='ana@example.com',
        password='secret123',
        first_name='Ana',
        last_name='Tester',
    )


@pytest.fixture
def other_professional():
    return Professional.objects.create_user(
        email='other-ana@example.com',
        password='secret123',
        first_name='Bea',
        last_name='Tester',
    )


@pytest.fixture
def foreign_professional():
    return Professional.objects.create_user(
        email='foreign-ana@example.com',
        password='secret123',
        first_name='Cleo',
        last_name='Tester',
    )


@pytest.fixture
def auth_client(professional):
    client = APIClient()
    client.force_authenticate(user=professional)
    return client


@pytest.fixture
def client_obj(professional):
    return Client.objects.create(
        professional=professional,
        first_name='Cliente',
        last_name='Teste',
        phone='19999999999',
    )


def test_bulk_save_rejects_field_from_other_professional(
    auth_client,
    professional,
    other_professional,
    client_obj,
):
    foreign_field = AnamnesisField.objects.create(
        professional=other_professional,
        code='takes_medication',
        sector='Histórico',
        sector_order=0,
        label='Toma medicação',
        field_type='radio',
        options=['Sim', 'Não'],
        order=0,
    )

    response = auth_client.post(
        '/anamnesis/responses/bulk_save/',
        {
            'client': client_obj.id,
            'responses': [
                {
                    'field': foreign_field.id,
                    'value': 'Sim',
                }
            ],
        },
        format='json',
    )

    assert response.status_code == 400, response.content
    assert 'não pertence ao profissional' in str(response.json()).lower()


def test_field_queryset_is_scoped_by_tenant(auth_client, professional, other_professional, foreign_professional):
    tenant = professional.tenant_memberships.first().tenant
    TenantMembership.objects.create(
        tenant=tenant,
        professional=other_professional,
        role=TenantMembership.Role.ADMIN,
        is_active=True,
    )

    shared_field = AnamnesisField.objects.create(
        professional=other_professional,
        code='shared_question',
        sector='Histórico',
        sector_order=0,
        label='Pergunta compartilhada',
        field_type='radio',
        options=['Sim', 'Não'],
        order=0,
    )

    foreign_field = AnamnesisField.objects.create(
        professional=foreign_professional,
        code='foreign_question',
        sector='Histórico',
        sector_order=0,
        label='Pergunta externa',
        field_type='radio',
        options=['Sim', 'Não'],
        order=1,
    )

    response = auth_client.get('/anamnesis/fields/')

    assert response.status_code == 200, response.content
    ids = {item['id'] for item in response.json()}
    assert shared_field.id in ids
    assert foreign_field.id not in ids


def test_bulk_save_rejects_client_from_other_tenant(
    auth_client,
    professional,
    foreign_professional,
):
    foreign_client = Client.objects.create(
        professional=foreign_professional,
        first_name='Cliente',
        last_name='Externo',
        phone='18888888888',
    )

    parent_field = AnamnesisField.objects.create(
        professional=professional,
        code='takes_medication',
        sector='Histórico',
        sector_order=0,
        label='Toma medicação',
        field_type='radio',
        options=['Sim', 'Não'],
        order=0,
    )

    response = auth_client.post(
        '/anamnesis/responses/bulk_save/',
        {
            'client': foreign_client.id,
            'responses': [
                {'field': parent_field.id, 'value': 'Sim'},
            ],
        },
        format='json',
    )

    assert response.status_code == 404, response.content


def test_bulk_save_deletes_missing_snapshot_responses(auth_client, professional, client_obj):
    parent_field = AnamnesisField.objects.create(
        professional=professional,
        code='takes_medication',
        sector='Histórico',
        sector_order=0,
        label='Toma medicação',
        field_type='radio',
        options=['Sim', 'Não'],
        order=0,
    )
    detail_field = AnamnesisField.objects.create(
        professional=professional,
        code='takes_medication_details',
        sector='Histórico',
        sector_order=0,
        label='Qual medicação?',
        field_type='text',
        order=1,
        depends_on=parent_field,
        show_when_value='Sim',
    )

    response = auth_client.post(
        '/anamnesis/responses/bulk_save/',
        {
            'client': client_obj.id,
            'responses': [
                {'field': parent_field.id, 'value': 'Sim'},
                {'field': detail_field.id, 'value': 'Dipirona'},
            ],
        },
        format='json',
    )
    assert response.status_code == 200, response.content
    assert AnamnesisResponse.objects.filter(client=client_obj).count() == 2

    response = auth_client.post(
        '/anamnesis/responses/bulk_save/',
        {
            'client': client_obj.id,
            'responses': [
                {'field': parent_field.id, 'value': 'Não'},
            ],
        },
        format='json',
    )
    assert response.status_code == 200, response.content

    remaining = AnamnesisResponse.objects.filter(client=client_obj)
    assert remaining.count() == 1
    assert remaining.get().field_id == parent_field.id
    assert remaining.get().value == 'Não'


def test_migrate_legacy_splits_yes_no_and_detail(professional):
    client = Client.objects.create(
        professional=professional,
        first_name='Maria',
        last_name='Legacy',
        phone='19888888888',
        takes_medication='Metformina',
        had_surgery='Joelho direito',
        is_pregnant=False,
    )

    seed_stdout = StringIO()
    call_command(
        'seed_anamnesis',
        professional_email=professional.email,
        stdout=seed_stdout,
    )

    migrate_stdout = StringIO()
    call_command(
        'migrate_anamnesis_legacy',
        professional_email=professional.email,
        stdout=migrate_stdout,
    )

    response_by_code = {
        response.field.code: response.value
        for response in AnamnesisResponse.objects.filter(client=client).select_related('field')
    }

    assert response_by_code['takes_medication'] == 'Sim'
    assert response_by_code['takes_medication_details'] == 'Metformina'
    assert response_by_code['had_surgery'] == 'Sim'
    assert response_by_code['had_surgery_details'] == 'Joelho direito'
    assert response_by_code['is_pregnant'] == 'Não'


def test_seed_reuses_legacy_field_labels_instead_of_creating_duplicates(professional):
    legacy_field = AnamnesisField.objects.create(
        professional=professional,
        code='toma_medicacao',
        sector='Histórico',
        sector_order=0,
        label='Toma medicação',
        field_type='radio',
        options=['Sim', 'Não'],
        order=2,
    )

    call_command(
        'seed_anamnesis',
        professional_email=professional.email,
        stdout=StringIO(),
    )

    updated_field = AnamnesisField.objects.get(pk=legacy_field.pk)
    assert updated_field.code == 'takes_medication'
    assert AnamnesisField.objects.filter(
        professional=professional,
        label='Toma medicação',
        sector='Histórico',
    ).count() == 1