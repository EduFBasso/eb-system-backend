from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.authentication.views.professional_views import (
    ProfessionalViewSet,
)
from apps.clinic.views.clients import ClientBasicViewSet, ClientViewSet


router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'clients-basic', ClientBasicViewSet, basename='client-basic')
router.register(r'professionals', ProfessionalViewSet)

urlpatterns = [
    path('', include(router.urls)),
]