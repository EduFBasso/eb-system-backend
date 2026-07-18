from django.core.management.base import BaseCommand

from apps.tenancy.backfill import backfill_existing_tenants


class Command(BaseCommand):
    help = 'Backfill nullable tenant fields from active TenantMembership records.'

    def handle(self, *args, **options):
        summary = backfill_existing_tenants()
        for label, updated_count in summary.items():
            self.stdout.write(f'{label}: {updated_count} updated')
        self.stdout.write(self.style.SUCCESS('Tenant backfill completed.'))
