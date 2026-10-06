from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


def health_view(_request):
    return JsonResponse({'status': 'ok'})


def full_health_view(_request):
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:
        db_ok = False
    return JsonResponse({
        'status': 'ok' if db_ok else 'degraded',
        'database': 'ok' if db_ok else 'error',
        'version': getattr(settings, 'APP_VERSION', 'unknown'),
        'time': timezone.now().isoformat(),
    })