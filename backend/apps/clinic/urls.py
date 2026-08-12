from django.urls import include, path

urlpatterns = [
    path('podology/', include('apps.clinic.views.podology_urls')),
    path('odonto/', include('apps.clinic.views.odonto_urls')),
]
