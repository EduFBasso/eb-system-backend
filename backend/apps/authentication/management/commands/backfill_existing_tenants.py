from django.core.management.base import BaseCommand
from django.db import transaction

from apps.authentication.services.backfill import backfill_existing_tenants


class Command(BaseCommand):
    help = "Preenche tenants ausentes em registros legados do Clinic."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula o backfill sem alterar registros.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        summary = backfill_existing_tenants(dry_run=dry_run)
        mode = "dry-run" if dry_run else "aplicado"

        self.stdout.write(f"Backfill de tenants ({mode}):")
        for model_name, count in summary.items():
            self.stdout.write(f"  {model_name}: {count}")
