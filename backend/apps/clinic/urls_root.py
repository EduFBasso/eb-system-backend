from django.urls import include, path


urlpatterns = [
    path("clinic/", include("apps.clinic.urls")),
    path("register/", include("apps.clinic.urls_registration")),
    path("agenda/", include("apps.clinic.views.agenda_urls")),
    path("inventory/", include("apps.clinic.views.inventory_urls")),
]