from __future__ import annotations

from uuid import uuid4

from django.conf import settings

from apps.authentication.models import DeviceSession, Professional


def resolve_device_id(value: str | None, user: Professional) -> str:
    device_id = (value or "").strip()[:64]
    return device_id or str(uuid4())


def activate_login_session(
    user: Professional,
    device_id: str,
    *,
    user_agent: str = "",
    ip_address: str | None = None,
) -> int:
    session, created = DeviceSession.objects.get_or_create(
        professional=user,
        device_id=device_id,
        defaults={
            "user_agent": user_agent[:255],
            "ip_address": ip_address,
            "is_active": True,
        },
    )
    if not created:
        session.is_active = True
        session.terminated_at = None
        session.termination_reason = ""
        session.user_agent = user_agent[:255]
        session.ip_address = ip_address
        session.save(
            update_fields=[
                "is_active",
                "terminated_at",
                "termination_reason",
                "user_agent",
                "ip_address",
            ]
        )

    active_qs = DeviceSession.objects.filter(professional=user, is_active=True)
    max_sessions = getattr(settings, "MAX_ACTIVE_DEVICE_SESSIONS", 2)
    active_count = active_qs.count()
    if active_count > max_sessions:
        overflow = active_count - max_sessions
        to_close = (
            active_qs.exclude(device_id=device_id)
            .order_by("last_seen_at")[:overflow]
        )
        for session_to_close in to_close:
            session_to_close.terminate(reason="limit")
        active_count = max_sessions

    return active_count
