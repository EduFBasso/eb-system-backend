from __future__ import annotations

from apps.authentication.models import Tenant, TenantMembership


def resolve_login_email(login: str, tenant: Tenant) -> str | None:
    """Resolve e-mail ou alias dentro de um tenant específico."""
    normalized_login = (login or "").strip()
    if "@" in normalized_login:
        return normalized_login.lower()

    membership = (
        TenantMembership.objects
        .select_related("professional")
        .filter(
            tenant=tenant,
            login_alias__iexact=normalized_login,
            is_active=True,
        )
        .first()
    )
    return membership.professional.email if membership else None