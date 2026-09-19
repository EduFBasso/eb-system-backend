# arquivo legado, preenche retroativamente o campo tenant nas tabelas que aceitam null 
# como a nova estrutura o tenant é obrigatório null=False em todos os models, não deve existir
# tenant = Null, portanto inútil para esta estrutura, mantido apenas para apagar posteriormente 
# em fase de limpeza de código, verificando se não há referencia que possa quebrar na importação.

from django.core.management.base import BaseCommand

from apps.authentication.services.backfill import backfill_existing_tenants


class Command(BaseCommand):
    help = 'Backfill nullable tenant fields from active TenantMembership records.'

    def handle(self, *args, **options):
        summary = backfill_existing_tenants()
        for label, updated_count in summary.items():
            self.stdout.write(f'{label}: {updated_count} updated')
        self.stdout.write(self.style.SUCCESS('Tenant backfill completed.'))
