from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from apps.register.models import Professional

from .models import Tenant, TenantMembership

_ODONTO_SPECIALTY_TOKENS = ("odonto", "dent", "ortodont")


def _supports_odonto(specialty: str) -> bool:
    normalized = (specialty or "").strip().lower()
    return any(token in normalized for token in _ODONTO_SPECIALTY_TOKENS)


def _build_tenant_slug(professional: Professional) -> str:
    base_name = slugify(
        professional.display_name
        or f"{professional.first_name} {professional.last_name}"
        or professional.email.split("@")[0]
        or "professional"
    )
    return f"professional-{professional.pk}-{base_name}"[:140]


def _build_tenant_name(professional: Professional) -> str:
    display = (professional.display_name or "").strip()
    if display:
        return f"Consultorio {display}"[:120]
    full_name = f"{professional.first_name} {professional.last_name}".strip()
    if full_name:
        return f"Consultorio {full_name}"[:120]
    return f"Consultorio {professional.email}"[:120]


@receiver(post_save, sender=Professional)
def create_tenant_for_new_professional(sender, instance: Professional, created: bool, **kwargs):
    if not created:
        return

    capabilities = {"odonto": True} if _supports_odonto(instance.specialty) else {}

    tenant, _ = Tenant.objects.get_or_create(
        slug=_build_tenant_slug(instance),
        defaults={
            "name": _build_tenant_name(instance),
            "capabilities": capabilities,
            "is_active": True,
        },
    )

    if tenant.capabilities != capabilities:
        tenant.capabilities = capabilities
        tenant.save(update_fields=["capabilities"])

    membership, _ = TenantMembership.objects.get_or_create(
        tenant=tenant,
        professional=instance,
        defaults={
            "role": TenantMembership.Role.ADMIN,
            "is_active": True,
        },
    )

    updates: list[str] = []
    if membership.role != TenantMembership.Role.ADMIN:
        membership.role = TenantMembership.Role.ADMIN
        updates.append("role")
    if not membership.is_active:
        membership.is_active = True
        updates.append("is_active")
    if updates:
        membership.save(update_fields=updates)
