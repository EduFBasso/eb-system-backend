import csv
import os

from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.utils import timezone

from apps.authentication.models.tenancy_models import Tenant
from apps.clinic.models.clients import Client


class Command(BaseCommand):
    help = "Exporta clientes cadastrados de uma clínica (Tenant) específica para um arquivo CSV."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--tenant-slug",
            dest="tenant_slug",
            required=True,
            help="Slug identificador da clínica (Tenant) obrigatório para isolamento de dados.",
        )
        parser.add_argument(
            "--out",
            dest="out",
            default="clients_export.csv",
            help="Caminho do arquivo de saída CSV (utilize '-' para exibir direto no terminal/stdout).",
        )

    def handle(self, *args, **options):
        tenant_slug = options["tenant_slug"].strip().lower()
        out = options["out"]

        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            raise CommandError(f"Erro: Empresa/Clínica (Tenant) com o slug '{tenant_slug}' não foi encontrada.")

        queryset = Client.objects.filter(tenant=tenant)
        fields = [
            "id", "first_name", "last_name", "phone", "email", "date_of_birth",
            "profession", "address", "address_number", "neighborhood", "city",
            "state", "postal_code", "created_at",
        ]
        rows = []
        for client in queryset.order_by("first_name", "last_name"):
            rows.append([
                client.id,
                client.first_name or "",
                client.last_name or "",
                client.phone or "",
                client.email or "",
                client.date_of_birth.isoformat() if client.date_of_birth else "",
                client.profession or "",
                client.address or "",
                client.address_number or "",
                client.neighborhood or "",
                client.city or "",
                client.state or "",
                client.postal_code or "",
                client.created_at.astimezone(timezone.utc).isoformat() if client.created_at else "",
            ])

        if out == "-":
            writer = csv.writer(self.stdout)
            writer.writerow(fields)
            writer.writerows(rows)
            return 0

        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(fields)
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Sucesso: Exportados {len(rows)} clientes da clínica '{tenant.name}' para o arquivo: {out}"
        ))
        return 0
