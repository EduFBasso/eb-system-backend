import pytest
from rest_framework.test import APIClient

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.clinic.models.anamnesis import AnamneseBase, AnamneseOdontologia
from apps.clinic.models.clients import Client


pytestmark = pytest.mark.django_db


def make_professional(email: str, slug: str):
    professional = Professional.objects.create_user(
        email=email,
        password='secret123',
        first_name='Dentista',
        last_name=slug,
    )
    professional.tenant_memberships.all().delete()
    tenant = Tenant.objects.create(
        name=f'Clínica {slug}',
        slug=slug,
        capabilities={'clinic': True, 'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    return professional, tenant


def test_dental_anamnesis_creates_fixed_base_and_specialty_records():
    professional, tenant = make_professional(
        'dentist-anamnesis@example.com',
        'dental-anamnesis',
    )
    client = Client.objects.create(
        tenant=tenant,
        first_name='Paciente',
        last_name='Odonto',
        phone='11990000001',
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/anamnesis/',
        {
            'client_id': client.id,
            'gum_bleeding': True,
            'floss_usage': False,
            'bruxism_clenching': True,
            'tooth_brushing_frequency': '3 vezes ao dia',
            'chief_dental_complaint': 'Sensibilidade',
        },
        format='json',
    )

    assert response.status_code == 201, response.content
    base = AnamneseBase.objects.get(client=client, tenant=tenant)
    specialty = AnamneseOdontologia.objects.get(anamnese_base=base)
    assert base.professional == professional
    assert specialty.professional == professional
    assert specialty.gum_bleeding is True
    assert specialty.chief_dental_complaint == 'Sensibilidade'


def test_dental_anamnesis_rejects_client_from_another_tenant():
    professional, _ = make_professional(
        'dentist-owner@example.com',
        'dental-owner',
    )
    _, foreign_tenant = make_professional(
        'dentist-foreign@example.com',
        'dental-foreign',
    )
    foreign_client = Client.objects.create(
        tenant=foreign_tenant,
        first_name='Paciente',
        last_name='Externo',
        phone='11990000002',
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/anamnesis/',
        {'client_id': foreign_client.id},
        format='json',
    )

    assert response.status_code == 400, response.content
    assert not AnamneseBase.objects.filter(client=foreign_client).exists()


def test_dental_anamnesis_rejects_tenant_without_odonto_capability():
    professional, tenant = make_professional(
        'podologist-anamnesis@example.com',
        'podology-anamnesis',
    )
    tenant.capabilities = {'clinic': True, 'podologia': True}
    tenant.save(update_fields=['capabilities'])
    client = Client.objects.create(
        tenant=tenant,
        first_name='Paciente',
        last_name='Podologia',
        phone='11990000003',
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/anamnesis/',
        {'client_id': client.id, 'gum_bleeding': True},
        format='json',
    )

    assert response.status_code == 403, response.content
    assert not AnamneseBase.objects.filter(client=client).exists()


def test_dental_anamnesis_ignores_bakery_membership_when_selecting_clinic():
    professional = Professional.objects.create_user(
        email='clinic-after-bakery@example.com',
        password='secret123',
        first_name='Dentista',
        last_name='Multisystem',
    )
    professional.tenant_memberships.all().delete()
    bakery = Tenant.objects.create(
        name='Padaria Separada',
        slug='bakery-before-clinic',
        ecosystem=Tenant.Ecosystem.BAKERY,
        capabilities={'bakery': True},
    )
    clinic = Tenant.objects.create(
        name='Clínica Odonto',
        slug='clinic-after-bakery',
        ecosystem=Tenant.Ecosystem.CLINIC,
        capabilities={'clinic': True, 'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=bakery,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    TenantMembership.objects.create(
        tenant=clinic,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    client = Client.objects.create(
        tenant=clinic,
        first_name='Paciente',
        last_name='Clínica',
        phone='11990000004',
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/anamnesis/',
        {'client_id': client.id, 'gum_bleeding': True},
        format='json',
    )

    assert response.status_code == 201, response.content
    assert AnamneseBase.objects.filter(client=client, tenant=clinic).exists()


def test_secondary_clinic_capability_does_not_authorize_active_clinic():
    professional = Professional.objects.create_user(
        email='two-clinics@example.com',
        password='secret123',
        first_name='Profissional',
        last_name='Multiclinic',
    )
    professional.tenant_memberships.all().delete()
    podologia = Tenant.objects.create(
        name='Clínica Podologia Ativa',
        slug='active-podology-clinic',
        capabilities={'clinic': True, 'podologia': True},
    )
    odonto = Tenant.objects.create(
        name='Clínica Odonto Secundária',
        slug='secondary-dental-clinic',
        capabilities={'clinic': True, 'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=podologia,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    TenantMembership.objects.create(
        tenant=odonto,
        professional=professional,
        role=TenantMembership.Role.OWNER,
        is_active=True,
    )
    client = Client.objects.create(
        tenant=podologia,
        first_name='Paciente',
        last_name='Podologia',
        phone='11990000005',
    )
    api = APIClient()
    api.force_authenticate(user=professional)

    response = api.post(
        '/clinic/treatment/anamnesis/',
        {'client_id': client.id, 'gum_bleeding': True},
        format='json',
    )

    assert response.status_code == 403, response.content
    assert not AnamneseBase.objects.filter(client=client).exists()