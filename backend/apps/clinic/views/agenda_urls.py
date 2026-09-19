from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .agenda import (
    AppointmentViewSet,
    ChargeViewSet,
    ClinicalRecordViewSet,
    EncounterViewSet,
)

router = DefaultRouter()
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'encounters', EncounterViewSet, basename='encounter')
router.register(r'clinical-records', ClinicalRecordViewSet, basename='clinical-record')
router.register(r'charges', ChargeViewSet, basename='charge')

urlpatterns = [
    path('', include(router.urls)),
]
