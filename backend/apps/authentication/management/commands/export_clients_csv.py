import csv
import os
from typing import Optional

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from apps.clinic.models.clients import Client
from apps.authentication.models import Professional


class Command(BaseCommand):
    help = "Exporta clientes para CSV (por profissional opcional)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--out",
            dest="out",
            default="clients_export.csv",
            help="Arquivo de saída CSV (use '-' para stdout)",
        )
        parser.add_argument(
            "--professional",
            dest="professional",
            default=None,
            help="E-mail do profissional para filtrar (opcional)",
        )

    def handle(self, *args, **options): # type: ignore
        out: str = options["out"]
        prof_email: Optional[str] = options.get("professional")

        qs = Client.objects.all().select_related("professional")
        if prof_email:
            try:
                prof = Professional.objects.get(email__iexact=prof_email)
            except Professional.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Profissional não encontrado: {prof_email}"))
                return 1
            qs = qs.filter(professional=prof)

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
                c.id, # type: ignore
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

        if out == "-":
            writer = csv.writer(self.stdout)
            writer.writerow(fields)
            writer.writerows(rows)
            return 0

        # Garante diretório
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"Exportado {len(rows)} clientes para {out}"))
        return 0
