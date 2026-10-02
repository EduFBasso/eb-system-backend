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
    path('api/v1/auth/bakery/login/', include('apps.authentication.urls_bakery_auth')),
    path('api/v1/bakery/', include('apps.bakery.urls', namespace='bakery')),
    path('clinic/', include('apps.clinic.urls')),
    path('register/', include('apps.clinic.urls_registration')),
    path('register/auth/', include('apps.authentication.urls_professional_registration')),
    path('agenda/', include('apps.clinic.views.agenda_urls')),
    path('inventory/', include('apps.clinic.views.inventory_urls')),

    # 🔐 Rotas globais de autenticação
    path('', include('apps.authentication.urls')),
]

if getattr(settings, 'SERVE_MEDIA_FILES', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
