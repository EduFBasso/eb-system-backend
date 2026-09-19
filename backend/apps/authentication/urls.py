from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.clinic.views.clients import ClientViewSet, ClientBasicViewSet
from .views.professional_views import (
    ProfessionalViewSet,
    ProfessionalBasicViewSet,
    professional_create,
)

router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'clients-basic', ClientBasicViewSet, basename='client-basic')
router.register(r'professionals', ProfessionalViewSet)
router.register(r'professionals-basic', ProfessionalBasicViewSet, basename='professional-basic')

urlpatterns = [
    path('auth/professional-create/', professional_create),
    path('', include(router.urls)),
]
