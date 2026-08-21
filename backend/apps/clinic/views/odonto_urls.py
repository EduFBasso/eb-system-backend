from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .odonto import TreatmentPlanViewSet, TreatmentPlanItemViewSet
from apps.clinic.views.anamnesis import DentalAnamnesisViewSet

router = DefaultRouter()
router.register(r'anamnesis', DentalAnamnesisViewSet, basename='odonto-anamnesis')
router.register(r'plans', TreatmentPlanViewSet, basename='odonto-plan')
router.register(r'items', TreatmentPlanItemViewSet, basename='odonto-item')

urlpatterns = [
    path('', include(router.urls)),
]
