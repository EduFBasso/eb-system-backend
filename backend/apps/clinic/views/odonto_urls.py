from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .odonto import DentalArcadeViewSet, ProcedureViewSet, SurfaceViewSet, ToothViewSet
from apps.clinic.views.anamnesis import DentalAnamnesisViewSet

router = DefaultRouter()
router.register(r'anamnesis', DentalAnamnesisViewSet, basename='odonto-anamnesis')
router.register(r'arcades', DentalArcadeViewSet, basename='odonto-arcade')
router.register(r'teeth', ToothViewSet, basename='odonto-tooth')
router.register(r'surfaces', SurfaceViewSet, basename='odonto-surface')
router.register(r'procedures', ProcedureViewSet, basename='odonto-procedure')

urlpatterns = [
    path('', include(router.urls)),
]
