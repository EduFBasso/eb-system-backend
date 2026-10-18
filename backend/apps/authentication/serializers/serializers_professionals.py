"""Compatibility imports for the former Clinic professional serializer module."""

from .clinic.professional import (
    CanManageClinicProfessionals,
    CanManageProfessionals,
    ClinicProfessionalSerializer,
    ProfessionalSerializer,
)

__all__ = [
    "CanManageClinicProfessionals",
    "CanManageProfessionals",
    "ClinicProfessionalSerializer",
    "ProfessionalSerializer",
]
