from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.apps import apps as django_apps


DIRECT_MODEL_SPECS = [
    ('clients', 'Client', 'professional_id'),
    ('agenda', 'Appointment', 'professional_id'),
    ('agenda', 'FinalizeAudit', 'professional_id'),
    ('agenda', 'Encounter', 'professional_id'),
    ('agenda', 'ClinicalRecord', 'professional_id'),
    ('agenda', 'Charge', 'professional_id'),
    ('odonto', 'DentalArcade', 'professional_id'),
    ('odonto', 'ProcedureNameSuggestion', 'professional_id'),
    ('odonto', 'ProductCatalogItem', 'professional_id'),
]

DERIVED_MODEL_SPECS = [
    ('agenda', 'ChargeItem', 'charge'),
    ('odonto', 'Tooth', 'arcade'),
    ('odonto', 'Surface', 'tooth__arcade'),
    ('odonto', 'Procedure', 'arcade'),
]


def _model(registry: Any, app_label: str, model_name: str) -> Any:
    return registry.get_model(app_label, model_name)


def _tenant_by_professional(registry: Any) -> dict[int, int]:
    TenantMembership = _model(registry, 'tenancy', 'TenantMembership')
    memberships_by_professional: dict[int, set[int]] = defaultdict(set)

    memberships = TenantMembership.objects.filter(
        is_active=True,
        tenant__is_active=True,
    ).values_list('professional_id', 'tenant_id')

    for professional_id, tenant_id in memberships:
        memberships_by_professional[professional_id].add(tenant_id)

    return {
        professional_id: next(iter(tenant_ids))
        for professional_id, tenant_ids in memberships_by_professional.items()
        if len(tenant_ids) == 1
    }


def _nested_attr(obj: Any, attr_path: str) -> Any:
    value = obj
    for attr in attr_path.split('__'):
        value = getattr(value, attr, None)
        if value is None:
            return None
    return value


def backfill_existing_tenants(registry: Any | None = None) -> dict[str, int]:
    registry = registry or django_apps
    tenant_by_professional = _tenant_by_professional(registry)
    summary: dict[str, int] = {}

    for app_label, model_name, professional_field in DIRECT_MODEL_SPECS:
        Model = _model(registry, app_label, model_name)
        updated_count = 0
        queryset = Model.objects.filter(tenant__isnull=True).only('id', professional_field)

        for instance in queryset.iterator():
            professional_id = getattr(instance, professional_field)
            tenant_id = tenant_by_professional.get(professional_id)
            if not tenant_id:
                continue
            updated_count += Model.objects.filter(
                pk=instance.pk,
                tenant__isnull=True,
            ).update(tenant_id=tenant_id)

        summary[f'{app_label}.{model_name}'] = updated_count

    for app_label, model_name, parent_path in DERIVED_MODEL_SPECS:
        Model = _model(registry, app_label, model_name)
        updated_count = 0
        queryset = Model.objects.filter(tenant__isnull=True).select_related(parent_path)

        for instance in queryset.iterator():
            parent = _nested_attr(instance, parent_path)
            tenant_id = getattr(parent, 'tenant_id', None)
            if not tenant_id:
                continue
            updated_count += Model.objects.filter(
                pk=instance.pk,
                tenant__isnull=True,
            ).update(tenant_id=tenant_id)

        summary[f'{app_label}.{model_name}'] = updated_count

    return summary
