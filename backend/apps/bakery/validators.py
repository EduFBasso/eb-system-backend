from apps.authentication.models import Tenant, TenantMembership


def has_duplicate_bakery_owner_name(
    first_name: str,
    last_name: str,
    exclude_professional_id: int | None = None,
) -> bool:
    """Verifica nomes duplicados entre owners ativos do ecossistema Bakery."""
    queryset = TenantMembership.objects.filter(
        tenant__ecosystem=Tenant.Ecosystem.BAKERY,
        role=TenantMembership.Role.OWNER,
        professional__first_name__iexact=(first_name or "").strip(),
        professional__last_name__iexact=(last_name or "").strip(),
    )
    if exclude_professional_id is not None:
        queryset = queryset.exclude(professional_id=exclude_professional_id)
    return queryset.exists()


__all__ = ["has_duplicate_bakery_owner_name"]
