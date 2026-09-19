from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.db import connection
from django.utils import timezone
from django.views.generic import RedirectView
from apps.authentication.services.authentication import EmailTokenObtainPairView
from apps.authentication.views.views_bakery_auth import BakeryTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
from apps.authentication.views.views_sessions import (
    sessions_summary,
    sessions_active,
    sessions_revoke,
)

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

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
    path('health/', health_view),  # liveness
    path('health', health_view),   # liveness (no slash)
    path('health/full', full_health_view),  # readiness + metadata
    path('admin/', admin.site.urls),
    path('api/v1/auth/bakery/login/', BakeryTokenObtainPairView.as_view(), name='bakery_token_obtain_pair'),
    path('api/v1/bakery/', include('apps.bakery.urls', namespace='bakery')),
    path('clinic/', include('apps.clinic.urls')),
    path('register/', include('apps.authentication.urls')),  # 🧩 Rotas do app clínico
    path('agenda/', include('apps.clinic.views.agenda_urls')),
    path('inventory/', include('apps.clinic.views.inventory_urls')),

    # 📱 Sessões de dispositivos (fase 1)
    path('sessions/summary', sessions_summary),
    path('sessions/active', sessions_active),
    path('sessions/revoke', sessions_revoke),

    # 🔐 JWT endpoints
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if getattr(settings, 'SERVE_MEDIA_FILES', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
