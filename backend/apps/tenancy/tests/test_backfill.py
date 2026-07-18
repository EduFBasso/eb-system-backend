from datetime import timedelta

import pytest
from django.utils import timezone

from apps.agenda.models import Appointment, Charge, ChargeItem
from apps.clients.models import Client
from apps.odonto.models import DentalArcade, Procedure, Surface, Tooth
from apps.register.models import Professional
from apps.tenancy.backfill import backfill_existing_tenants
from apps.tenancy.models import Tenant, TenantMembership


pytestmark = pytest.mark.django_db


@pytest.fixture
def professional():
    return Professional.objects.create_user(
        email='backfill-professional@example.com',
        password='secret123',
        first_name='Backfill',
        last_name='Professional',
    )


@pytest.fixture
def tenant(professional):
    tenant = Tenant.objects.create(
        name='Backfill Tenant',
        slug='backfill-tenant',
        capabilities={'odonto': True},
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=professional,
        role=TenantMembership.Role.OWNER,
    )
    return tenant


def test_backfill_sets_tenant_on_direct_and_derived_models(professional, tenant):
    client = Client.objects.create(
        professional=professional,
        first_name='Backfill',
        last_name='Client',
        phone='11973001001',
    )
    appointment = Appointment.objects.create(
        professional=professional,
        client=client,
        title='Consulta',
        start_at=timezone.now(),
        end_at=timezone.now() + timedelta(hours=1),
    )
    charge = Charge.objects.create(
        professional=professional,
        client=client,
        appointment=appointment,
        title='Cobrança',
    )
    charge_item = ChargeItem.objects.create(
        charge=charge,
        item_type=ChargeItem.ItemType.CUSTOM,
        description='Item avulso',
    )
    arcade = DentalArcade.objects.create(professional=professional, client=client)
    tooth = Tooth.objects.create(arcade=arcade, sequence=1, international_number=11)
    surface = Surface.objects.create(tooth=tooth, code=Surface.SurfaceCode.O)
    procedure = Procedure.objects.create(
        arcade=arcade,
        tooth=tooth,
        surface=surface,
        name='Procedimento',
    )

    summary = backfill_existing_tenants()

    assert summary['clients.Client'] == 1
    assert summary['agenda.Appointment'] == 1
    assert summary['agenda.Charge'] == 1
    assert summary['agenda.ChargeItem'] == 1
    assert summary['odonto.DentalArcade'] == 1
    assert summary['odonto.Tooth'] == 1
    assert summary['odonto.Surface'] == 1
    assert summary['odonto.Procedure'] == 1

    for instance in [
        client,
        appointment,
        charge,
        charge_item,
        arcade,
        tooth,
        surface,
        procedure,
    ]:
        instance.refresh_from_db()
        assert instance.tenant_id == tenant.id


def test_backfill_skips_professional_with_multiple_active_tenants(professional):
    first_tenant = Tenant.objects.create(name='First Tenant', slug='first-tenant')
    second_tenant = Tenant.objects.create(name='Second Tenant', slug='second-tenant')
    TenantMembership.objects.create(
        tenant=first_tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
    )
    TenantMembership.objects.create(
        tenant=second_tenant,
        professional=professional,
        role=TenantMembership.Role.MEMBER,
    )
    client = Client.objects.create(
        professional=professional,
        first_name='Ambiguous',
        last_name='Client',
        phone='11973001002',
    )

    summary = backfill_existing_tenants()

    assert summary['clients.Client'] == 0
    client.refresh_from_db()
    assert client.tenant_id is None