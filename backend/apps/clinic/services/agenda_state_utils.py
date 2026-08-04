from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Appointment


def promote_scheduled_to_ongoing(
    base_qs: QuerySet | None = None,
) -> int:
    """Promote scheduled appointments that have started but not yet ended to ongoing.

    Opportunistic: called during list/next_for_client to keep status current.
    Only affects appointments where start_at <= now < end_at.
    """
    now = timezone.now()
    qs = base_qs if base_qs is not None else Appointment.objects.all()
    return qs.filter(
        status=Appointment.Status.SCHEDULED,
        start_at__lte=now,
        end_at__gt=now,
    ).update(
        status=Appointment.Status.ONGOING,
        updated_at=now,
    )


def promote_overdue_scheduled_to_pending(
    base_qs: QuerySet | None = None,
) -> int:
    """Promote overdue scheduled/ongoing appointments to pending.

    This is an opportunistic promotion used until a periodic job is introduced.
    It affects appointments that have already ended (end_at < now) and are
    still in scheduled or ongoing state.
    """
    now = timezone.now()
    qs = base_qs if base_qs is not None else Appointment.objects.all()
    return qs.filter(
        Q(status=Appointment.Status.SCHEDULED) | Q(status=Appointment.Status.ONGOING),
        end_at__lt=now,
    ).update(
        status=Appointment.Status.PENDING,
        updated_at=now,
    )
