from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .anamnesis import AnamnesisFieldViewSet, AnamnesisResponseViewSet

router = DefaultRouter()
router.register(r'fields', AnamnesisFieldViewSet, basename='anamnesis-field')
router.register(r'responses', AnamnesisResponseViewSet, basename='anamnesis-response')

urlpatterns = [
    path('', include(router.urls)),
]
