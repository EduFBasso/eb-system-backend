from django.urls import include, path


urlpatterns = [
    path("api/v1/bakery/", include("apps.bakery.urls", namespace="bakery")),
]