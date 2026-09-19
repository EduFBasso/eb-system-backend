import csv

import pytest
from django.core.management import call_command

from apps.authentication.models import Tenant
from apps.clinic.models import Client


pytestmark = pytest.mark.django_db


def test_import_uses_phone_when_emails_are_repeated(tmp_path):
    tenant = Tenant.objects.create(
        name="Clinica Importacao",
        trade_name="Clinica Importacao",
        slug="clinica-importacao",
    )
    csv_path = tmp_path / "clients.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["first_name", "last_name", "email", "phone"])
        writer.writeheader()
        writer.writerows([
            {"first_name": "Ana", "last_name": "A", "email": "shared@example.test", "phone": "11911111111"},
            {"first_name": "Bia", "last_name": "B", "email": "shared@example.test", "phone": "11922222222"},
        ])

    call_command(
        "import_clients_csv",
        file=str(csv_path),
        tenant_slug=tenant.slug,
        skip_anamnesis=True,
    )

    clients = Client.objects.filter(tenant=tenant).order_by("phone")
    assert clients.count() == 2
    assert list(clients.values_list("phone", flat=True)) == ["11911111111", "11922222222"]
    assert clients.filter(email="shared@example.test").count() == 1