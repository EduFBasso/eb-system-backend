from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.views_webauthn import (
    webauthn_register_begin,
    webauthn_register_complete,
    webauthn_login_begin,
    webauthn_login_complete,
)
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
    path('auth/webauthn/register-begin/', webauthn_register_begin),
    path('auth/webauthn/register-complete/', webauthn_register_complete),
    path('auth/webauthn/login-begin/', webauthn_login_begin),
    path('auth/webauthn/login-complete/', webauthn_login_complete),
    path('', include(router.urls)),
]
