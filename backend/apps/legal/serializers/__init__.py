from .cases import LegalCasePartySerializer, LegalCaseSerializer, LegalRepresentationSerializer
from .clients import LegalClientSerializer
from .lawyers import LegalLawyerProfileSerializer
from .persons import LegalPersonSerializer

__all__ = [
    "LegalCasePartySerializer",
    "LegalCaseSerializer",
    "LegalClientSerializer",
    "LegalLawyerProfileSerializer",
    "LegalPersonSerializer",
    "LegalRepresentationSerializer",
]
