import pytest

from apps.authentication.models import SystemUser
from apps.authentication.serializers.clinic.professional import (
    ClinicProfessionalSerializer,
)
from apps.authentication.serializers.clinic.settings import ProfessionalSettingsSerializer


def test_settings_serializer_rejects_invalid_work_interval():
    serializer = ProfessionalSettingsSerializer(data={
        "work_start_hour": 18,
        "work_start_minute": 0,
        "work_end_hour": 8,
        "work_end_minute": 0,
    })

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


def test_settings_serializer_allows_midnight_end_only_at_zero_minutes():
    valid_serializer = ProfessionalSettingsSerializer(data={
        "work_start_hour": 8,
        "work_start_minute": 30,
        "work_end_hour": 24,
        "work_end_minute": 0,
    })
    invalid_serializer = ProfessionalSettingsSerializer(data={
        "work_start_hour": 8,
        "work_start_minute": 30,
        "work_end_hour": 24,
        "work_end_minute": 15,
    })

    assert valid_serializer.is_valid()
    assert not invalid_serializer.is_valid()
    assert "work_end_minute" in invalid_serializer.errors


@pytest.mark.parametrize("slot_minutes", [1, 25, 75])
def test_settings_serializer_rejects_unsupported_slot_minutes(slot_minutes):
    serializer = ProfessionalSettingsSerializer(data={"slot_minutes": slot_minutes})

    assert not serializer.is_valid()
    assert "slot_minutes" in serializer.errors


@pytest.mark.django_db
def test_clinic_professional_serializer_protects_administrative_fields():
    user = SystemUser.objects.create_user(
        email="professional-fields@example.com",
        password="senha-segura-123",
    )

    serializer = ClinicProfessionalSerializer(
        user,
        data={
            "is_superuser": True,
            "is_staff": True,
            "can_manage_professionals": True,
            "is_active": False,
        },
        partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    user.refresh_from_db()
    assert user.is_superuser is False
    assert user.is_staff is False
    assert user.can_manage_professionals is False
    assert user.is_active is True
