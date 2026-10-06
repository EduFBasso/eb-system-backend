from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import DeviceSession


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
    device_id = f"test-device-{professional.pk}"
    DeviceSession.objects.update_or_create(
        professional=professional,
        device_id=device_id,
        defaults={"is_active": True},
    )
    token["tenant_id"] = membership.tenant_id
    token["ecosystem"] = "clinic"
    token["device_id"] = device_id
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client
