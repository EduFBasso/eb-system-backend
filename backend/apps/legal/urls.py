from rest_framework.routers import DefaultRouter

from apps.legal.views import (
    LegalCasePartyViewSet,
    LegalCaseViewSet,
    LegalClientViewSet,
    LegalLawyerProfileViewSet,
    LegalPersonViewSet,
    LegalRepresentationViewSet,
)

router = DefaultRouter()
router.register("people", LegalPersonViewSet, basename="legal-person")
router.register("clients", LegalClientViewSet, basename="legal-client")
router.register("lawyers", LegalLawyerProfileViewSet, basename="legal-lawyer")
router.register("cases", LegalCaseViewSet, basename="legal-case")
router.register("case-parties", LegalCasePartyViewSet, basename="legal-case-party")
router.register(
    "representations",
    LegalRepresentationViewSet,
    basename="legal-representation",
)

urlpatterns = router.urls
