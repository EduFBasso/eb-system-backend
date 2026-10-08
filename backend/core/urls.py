from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core.health import full_health_view, health_view

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
    path('health/', health_view),  # liveness
    path('health', health_view),   # liveness (no slash)
    path('health/full', full_health_view),  # readiness + metadata
    path('admin/', admin.site.urls),
    path('', include('apps.authentication.urls')),
    path('', include('apps.clinic.urls_root')),
    path('api/v1/clinic/', include('apps.clinic.urls_api_v1', namespace='clinic-v1')),
    path('', include('apps.bakery.urls_root')),
]

if getattr(settings, 'SERVE_MEDIA_FILES', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
