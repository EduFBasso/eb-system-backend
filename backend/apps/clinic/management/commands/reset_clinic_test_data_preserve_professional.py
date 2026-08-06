from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clinic.models.clients import Client
from apps.clinic.models.odonto import (
    DentalArcade,
    Procedure,
    ProcedureNameSuggestion,
    ProductCatalogItem,
    Surface,
    Tooth,
)
from apps.authentication.models import Professional


class Command(BaseCommand):
    help = (
        'Reseta dados de teste de clientes + odonto preservando login/profissional. '
        'Por padrao executa dry-run; use --execute para aplicar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--professional-id',
            type=int,
            help='ID do profissional alvo. Obrigatorio, exceto com --all-professionals.',
        )
        parser.add_argument(
            '--all-professionals',
            action='store_true',
            help='Aplica para todos os profissionais (use com cautela).',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Aplica a exclusao. Sem esta flag o comando apenas simula.',
        )

    def handle(self, *args, **options):
        professional_id = options.get('professional_id')
        all_professionals = options.get('all_professionals', False)
        execute = options.get('execute', False)

        if not all_professionals and not professional_id:
            raise CommandError(
                'Informe --professional-id ou use --all-professionals.',
            )

        if all_professionals and professional_id:
            raise CommandError(
                'Use apenas --professional-id ou --all-professionals, nao ambos.',
            )

        prof_qs = Professional.objects.all()
        if professional_id:
            prof_qs = prof_qs.filter(id=professional_id)
            if not prof_qs.exists():
                raise CommandError(f'Profissional {professional_id} nao encontrado.')

        prof_ids = list(prof_qs.values_list('id', flat=True))

        client_qs = Client.objects.filter(professional_id__in=prof_ids)
        arcade_qs = DentalArcade.objects.filter(professional_id__in=prof_ids)
        tooth_qs = Tooth.objects.filter(arcade__professional_id__in=prof_ids)
        surface_qs = Surface.objects.filter(tooth__arcade__professional_id__in=prof_ids)
        procedure_qs = Procedure.objects.filter(arcade__professional_id__in=prof_ids)
        procedure_suggestion_qs = ProcedureNameSuggestion.objects.filter(
            professional_id__in=prof_ids,
        )
        product_catalog_qs = ProductCatalogItem.objects.filter(
            professional_id__in=prof_ids,
        )

        summary = {
            'professionals_targeted': len(prof_ids),
            'clients': client_qs.count(),
            'arcades': arcade_qs.count(),
            'teeth': tooth_qs.count(),
            'surfaces': surface_qs.count(),
            'procedures': procedure_qs.count(),
            'procedure_name_suggestions': procedure_suggestion_qs.count(),
            'product_catalog_items': product_catalog_qs.count(),
            'professionals_total_preserved': Professional.objects.count(),
            'users_total_preserved': get_user_model().objects.count(),
        }

        self.stdout.write('Resumo do reset (escopo alvo):')
        for key, value in summary.items():
            self.stdout.write(f'- {key}: {value}')

        if not execute:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Dry-run finalizado. Nada foi alterado. Use --execute para aplicar.',
                )
            )
            return

        with transaction.atomic():
            deleted_suggestions = procedure_suggestion_qs.delete()[0]
            deleted_catalog = product_catalog_qs.delete()[0]
            # Excluir clientes remove cascata de odonto associada aos clientes.
            deleted_clients = client_qs.delete()[0]
            # Garantia: remove eventuais odonto orfaos por profissional.
            deleted_arcades = arcade_qs.delete()[0]

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Reset aplicado com sucesso.'))
        self.stdout.write(f'- registros removidos (clientes + cascatas): {deleted_clients}')
        self.stdout.write(f'- registros removidos (arcadas remanescentes): {deleted_arcades}')
        self.stdout.write(f'- sugestoes removidas: {deleted_suggestions}')
        self.stdout.write(f'- catalogo removido: {deleted_catalog}')
        self.stdout.write(
            f'- profissionais preservados: {Professional.objects.count()}'
        )
        self.stdout.write(f'- usuarios preservados: {get_user_model().objects.count()}')
