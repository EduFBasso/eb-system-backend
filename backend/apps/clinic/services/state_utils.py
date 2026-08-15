from django.db.models import QuerySet
from django.utils import timezone

from apps.clinic.models.agenda import Appointment


def promote_overdue_scheduled_to_pending(
    base_qs: QuerySet | None = None,
) -> int:
    """Promote overdue scheduled appointments to pending.

    This is an opportunistic promotion used until a periodic job is introduced.
    It affects appointments that have already ended (end_at < now) and are
    still in scheduled state.
    """
    now = timezone.now()
    qs = base_qs if base_qs is not None else Appointment.objects.all()
    return qs.filter(
        status=Appointment.Status.SCHEDULED,
        end_at__lt=now,
    ).update(
        status=Appointment.Status.PENDING,
        updated_at=now,
    )