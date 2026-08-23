from django.urls import include, path

urlpatterns = [
    path('agenda/', include('apps.clinic.views.agenda_urls')),
    path('inventory/', include('apps.clinic.views.inventory_urls')),
]
