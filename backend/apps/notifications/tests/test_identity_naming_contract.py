import pytest
from django.apps import apps

from apps.authentication.models import SystemUser
from apps.notifications.models import TelegramProfessionalLink


def test_systemuser_is_the_only_current_authentication_identity():
    assert apps.get_model("authentication", "SystemUser") is SystemUser

    with pytest.raises(LookupError):
        apps.get_model("authentication", "Professional")


def test_telegram_link_preserves_domain_field_and_legacy_table_contract():
    professional_field = TelegramProfessionalLink._meta.get_field("professional")

    assert TelegramProfessionalLink._meta.app_label == "notifications"
    assert TelegramProfessionalLink._meta.db_table == "clinic_telegramprofessionallink"
    assert professional_field.remote_field.model is SystemUser
