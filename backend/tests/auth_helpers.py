from rest_framework_simplejwt.tokens import AccessToken


def authenticate_clinic_client(client, professional):
    membership = (
        professional.tenant_memberships
        .select_related("tenant")
        .filter(
            is_active=True,
            tenant__is_active=True,
            tenant__ecosystem="clinic",
        )
        .order_by("created_at", "id")
        .first()
    )
    assert membership is not None

    token = AccessToken.for_user(professional)
    token["tenant_id"] = membership.tenant_id
    token["ecosystem"] = "clinic"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client
