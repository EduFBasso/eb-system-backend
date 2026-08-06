import pytest
from rest_framework.test import APIClient

from apps.clinic.models.anamnesis import AnamnesisField, AnamnesisResponse
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional
from apps.authentication.models import Tenant, TenantMembership


pytestmark = pytest.mark.django_db


def _ensure_default_dynamic_fields(professional):
    """Cria/atualiza apenas os campos usados nestes testes de anamnese dinâmica."""
    fields = [
        {
            'code': 'takes_medication',
            'label': 'Toma medicação',
            'field_type': 'radio',
            'options': ['Sim', 'Não'],
            'order': 0,
            'depends_on': None,
            'show_when_value': '',
        },
        {
            'code': 'takes_medication_details',
            'label': 'Qual medicação?',
            'field_type': 'text',
            'options': None,
            'order': 1,
            'depends_on': 'takes_medication',
            'show_when_value': 'Sim',
        },
        {
            'code': 'had_surgery',
            'label': 'Fez cirurgia?',
            'field_type': 'radio',
            'options': ['Sim', 'Não'],
            'order': 2,
            'depends_on': None,
            'show_when_value': '',
        },
        {
            'code': 'had_surgery_details',
            'label': 'Qual cirurgia?',
            'field_type': 'text',
            'options': None,
            'order': 3,
            'depends_on': 'had_surgery',
            'show_when_value': 'Sim',
        },
        {
            'code': 'is_pregnant',
            'label': 'Está grávida?',
            'field_type': 'radio',
            'options': ['Sim', 'Não'],
            'order': 4,
            'depends_on': None,
            'show_when_value': '',
        },
    ]

    by_code = {}
    for field_data in fields:
        obj, _ = AnamnesisField.objects.update_or_create(
            professional=professional,
            code=field_data['code'],
            defaults={
                'sector': 'Histórico',
                'sector_order': 0,
                'label': field_data['label'],
                'field_type': field_data['field_type'],
                'selection_mode': 'single',
                'options': field_data['options'],
                'placeholder': '',
                'show_when_value': field_data['show_when_value'],
                'order': field_data['order'],
                'is_active': True,
            },
        )
        by_code[field_data['code']] = obj

    for field_data in fields:
        code = field_data['code']
        depends_on_code = field_data['depends_on']
        obj = by_code[code]
        obj.depends_on = by_code.get(depends_on_code) if depends_on_code else None
        obj.show_when_value = field_data['show_when_value']
        obj.save(update_fields=['depends_on', 'show_when_value'])


def _migrate_legacy_field_labels(professional):
    legacy_to_canonical = {
        'toma_medicacao': 'takes_medication',
    }
    for legacy_code, canonical_code in legacy_to_canonical.items():
        legacy = AnamnesisField.objects.filter(
            professional=professional,
            code=legacy_code,
        ).first()
        if not legacy:
            continue
        canonical = AnamnesisField.objects.filter(
            professional=professional,
            code=canonical_code,
        ).exclude(pk=legacy.pk).first()
        if canonical:
            canonical.delete()
        legacy.code = canonical_code
        legacy.is_active = True
        legacy.save(update_fields=['code', 'is_active'])


@pytest.fixture
def professional():
    professional = Professional.objects.create_user(
        email='ana@example.com',
        password='secret123',
        first_name='Ana',
        last_name='Tester',
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Ana', slug='tenant-ana')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def other_professional():
    professional = Professional.objects.create_user(
        email='other-ana@example.com',
        password='secret123',
        first_name='Bea',
        last_name='Tester',
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Bea', slug='tenant-bea')
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional


@pytest.fixture
def foreign_professional():
    professional = Professional.objects.create_user(
        email='foreign-ana@example.com',
        password='secret123',
        first_name='Cleo',
        last_name='Tester',
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(name='Tenant Cleo', slug='tenant-cleo')
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
    client.force_authenticate(user=professional)
    return client


@pytest.fixture
def client_obj(professional):
    tenant = professional.tenant_memberships.first().tenant
    return Client.objects.create(
        tenant=tenant,
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
        tenant=foreign_professional.tenant_memberships.first().tenant,
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


def test_migrate_legacy_splits_yes_no_and_detail(auth_client, professional):
    tenant = professional.tenant_memberships.first().tenant
    client = Client.objects.create(
        tenant=tenant,
        professional=professional,
        first_name='Maria',
        last_name='Legacy',
        phone='19888888888',
    )

    _ensure_default_dynamic_fields(professional)

    field_map = {
        field.code: field.id
        for field in AnamnesisField.objects.filter(
            professional=professional,
            code__in=[
                'takes_medication',
                'takes_medication_details',
                'had_surgery',
                'had_surgery_details',
                'is_pregnant',
            ],
        )
    }

    response = auth_client.post(
        '/anamnesis/responses/bulk_save/',
        {
            'client': client.id,
            'responses': [
                {'field': field_map['takes_medication'], 'value': 'Sim'},
                {
                    'field': field_map['takes_medication_details'],
                    'value': 'Metformina',
                },
                {'field': field_map['had_surgery'], 'value': 'Sim'},
                {
                    'field': field_map['had_surgery_details'],
                    'value': 'Joelho direito',
                },
                {'field': field_map['is_pregnant'], 'value': 'Não'},
            ],
        },
        format='json',
    )
    assert response.status_code == 200, response.content

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

    _ensure_default_dynamic_fields(professional)
    _migrate_legacy_field_labels(professional)

    updated_field = AnamnesisField.objects.get(pk=legacy_field.pk)
    assert updated_field.code == 'takes_medication'
    assert AnamnesisField.objects.filter(
        professional=professional,
        label='Toma medicação',
        sector='Histórico',
    ).count() == 1