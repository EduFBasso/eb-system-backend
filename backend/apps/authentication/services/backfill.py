from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.apps import apps as django_apps


DIRECT_MODEL_SPECS = [
    ('clinic', 'Appointment', 'professional_id'),
    ('clinic', 'Encounter', 'professional_id'),
    ('clinic', 'ClinicalRecord', 'professional_id'),
    ('clinic', 'Charge', 'professional_id'),
    ('clinic', 'AnamneseBase', 'professional_id'),
    ('clinic', 'ReminderDelivery', 'professional_id'),
    ('clinic', 'TreatmentPlan', 'professional_id'),
]

DERIVED_MODEL_SPECS = [
    ('clinic', 'ChargeItem', 'charge'),
    ('clinic', 'PodologyProcedureContext', 'treatment_plan_item__plan'),
]


def _model(registry: Any, app_label: str, model_name: str) -> Any:
    return registry.get_model(app_label, model_name)


def _tenant_by_professional(registry: Any) -> dict[int, int]:
    TenantMembership = _model(registry, 'authentication', 'TenantMembership')
    memberships_by_professional: dict[int, set[int]] = defaultdict(set)

    memberships = TenantMembership.objects.filter(
        is_active=True,
        tenant__is_active=True,
        tenant__ecosystem='clinic',
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


def backfill_existing_tenants(
    registry: Any | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Preenche tenants legados sem reatribuir registros ambíguos.

    Em ``dry_run`` retorna a quantidade de registros elegíveis, mas não
    executa atualizações.
    """
    registry = registry or django_apps
    tenant_by_professional = _tenant_by_professional(registry)
    summary: dict[str, int] = {}
    inferred_tenants: dict[tuple[str, int], int] = {}

    for app_label, model_name, professional_field in DIRECT_MODEL_SPECS:
        Model = _model(registry, app_label, model_name)
        model_label = f'{app_label}.{model_name}'.lower()
        updated_count = 0
        queryset = Model.objects.filter(tenant__isnull=True).only('id', professional_field)

        for instance in queryset.iterator():
            professional_id = getattr(instance, professional_field)
            tenant_id = tenant_by_professional.get(professional_id)
            if not tenant_id:
                continue
            if dry_run:
                inferred_tenants[(model_label, instance.pk)] = tenant_id
                updated_count += 1
            else:
                changed_count = Model.objects.filter(
                    pk=instance.pk,
                    tenant__isnull=True,
                ).update(tenant_id=tenant_id)
                updated_count += changed_count
                if changed_count:
                    inferred_tenants[(model_label, instance.pk)] = tenant_id

        summary[f'{app_label}.{model_name}'] = updated_count

    for app_label, model_name, parent_path in DERIVED_MODEL_SPECS:
        Model = _model(registry, app_label, model_name)
        model_label = f'{app_label}.{model_name}'.lower()
        updated_count = 0
        queryset = Model.objects.filter(tenant__isnull=True).select_related(parent_path)

        for instance in queryset.iterator():
            parent = _nested_attr(instance, parent_path)
            tenant_id = getattr(parent, 'tenant_id', None)
            if tenant_id is None and parent is not None:
                parent_model_label = parent._meta.label_lower
                tenant_id = inferred_tenants.get((parent_model_label, parent.pk))
            if not tenant_id:
                continue
            if dry_run:
                inferred_tenants[(model_label, instance.pk)] = tenant_id
                updated_count += 1
            else:
                changed_count = Model.objects.filter(
                    pk=instance.pk,
                    tenant__isnull=True,
                ).update(tenant_id=tenant_id)
                updated_count += changed_count
                if changed_count:
                    inferred_tenants[(model_label, instance.pk)] = tenant_id

        summary[f'{app_label}.{model_name}'] = updated_count

    return summary
