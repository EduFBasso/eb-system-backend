# backend/apps/authentication/management/commands/export_clients_csv.py
import csv
import os
from typing import Optional

from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.utils import timezone

from apps.clinic.models.clients import Client
from apps.authentication.models.tenancy_models import Tenant


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
        tenant_slug: str = options["tenant_slug"].strip().lower()
        out: str = options["out"]

        # [Segurança Multi-tenant] Garante que a exportação só ocorra se a clínica for explicitamente localizada
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            raise CommandError(f"Erro: Empresa/Clínica (Tenant) com o slug '{tenant_slug}' não foi encontrada.")

        # Realiza a query filtrando estritamente pelos clientes que pertencem a este Tenant
        qs = Client.objects.filter(tenant=tenant)

        fields = [
            "id",
            "first_name",
            "last_name",
            "phone",
            "email",
            "date_of_birth",
            "profession",
            "address",
            "address_number",
            "neighborhood",
            "city",
            "state",
            "postal_code",
            "created_at",
        ]

        rows = []
        for c in qs.order_by("first_name", "last_name"):
            rows.append([
                c.id,
                c.first_name or "",
                c.last_name or "",
                c.phone or "",
                c.email or "",
                c.date_of_birth.isoformat() if c.date_of_birth else "",
                c.profession or "",
                c.address or "",
                c.address_number or "",
                c.neighborhood or "",
                c.city or "",
                c.state or "",
                c.postal_code or "",
                c.created_at.astimezone(timezone.utc).isoformat() if c.created_at else "",
            ])

        # Direciona o fluxo caso o usuário queira printar direto no terminal
        if out == "-":
            writer = csv.writer(self.stdout)
            writer.writerow(fields)
            writer.writerows(rows)
            return 0

        # Cria a pasta de destino caso ela não exista fisicamente na máquina
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Sucesso: Exportados {len(rows)} clientes da clínica '{tenant.name}' para o arquivo: {out}"
        ))
        return 0
