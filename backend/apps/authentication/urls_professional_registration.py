from django.urls import path

from apps.authentication.views.professional_views import professional_create


urlpatterns = [
    path('professional-create/', professional_create),
]