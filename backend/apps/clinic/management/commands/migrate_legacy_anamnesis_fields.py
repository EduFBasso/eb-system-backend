"""
Management command: migrate_anamnesis_legacy

Reads the legacy anamnesis fields from apps.clinic.models.clients.Client and creates
AnamnesisResponse records for each non-empty value found.

Prerequisites:
    - seed_anamnesis must have been run first for this professional
      (AnamnesisField records must exist with matching labels)

Usage:
    python manage.py migrate_anamnesis_legacy --professional-email=podologa@clinica.com
    python manage.py migrate_anamnesis_legacy --professional-email=podologa@clinica.com --dry-run

After verifying results, the legacy columns on Client can be removed in a future migration (Phase 2).
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clinic.models.anamnesis import AnamnesisField, AnamnesisResponse
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional


LEGACY_FIELD_MAP = [
    ('sport_activity', 'sport_activity'),
    ('academic_activity', 'academic_activity'),
    ('pain_sensitivity', 'pain_sensitivity'),
    ('clinical_history', 'clinical_history'),
    ('footwear_used', 'footwear_used'),
    ('sock_used', 'sock_used'),
    ('plantar_view_right', 'plantar_view_right'),
    ('dermatological_pathologies_right', 'dermatological_pathologies_right'),
    ('nail_changes_right', 'nail_changes_right'),
    ('deformities_right', 'deformities_right'),
    ('sensitivity_test', 'sensitivity_test'),
    ('plantar_view_left', 'plantar_view_left'),
    ('dermatological_pathologies_left', 'dermatological_pathologies_left'),
    ('nail_changes_left', 'nail_changes_left'),
    ('deformities_left', 'deformities_left'),
    ('other_procedures', 'other_procedures'),
]

DETAIL_FIELD_MAP = [
    ('takes_medication', 'takes_medication', 'takes_medication_details'),
    ('had_surgery', 'had_surgery', 'had_surgery_details'),
]

IS_PREGNANT_CODE = 'is_pregnant'


def normalize_yes_no_with_detail(raw_value):
    if raw_value is None:
        return None, None

    if isinstance(raw_value, bool):
        return ('Sim' if raw_value else 'Não'), None

    value = str(raw_value).strip()
    if not value:
        return None, None

    normalized = value.lower()
    if normalized in {'sim', 'não', 'nao'}:
        return ('Sim' if normalized == 'sim' else 'Não'), None

    return 'Sim', value


class Command(BaseCommand):
    help = 'Migra dados de anamnese legados do modelo Client para AnamnesisResponse'

    def add_arguments(self, parser):
        parser.add_argument(
            '--professional-email',
            required=True,
            help='E-mail do profissional cujos clientes serão migrados',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria criado sem salvar no banco',
        )

    def handle(self, *args, **options):
        email = options['professional_email']
        dry_run = options['dry_run']

        try:
            professional = Professional.objects.get(email=email)
        except Professional.DoesNotExist:
            raise CommandError(f'Profissional "{email}" não encontrado.')

        self.stdout.write(
            self.style.SUCCESS(
                f'Profissional: {professional.first_name} {professional.last_name} (id={professional.pk})'
            )
        )

        # Build code → AnamnesisField lookup for this professional
        fields_qs = AnamnesisField.objects.filter(professional=professional)
        field_by_code = {f.code: f for f in fields_qs}

        if not field_by_code:
            raise CommandError(
                'Nenhum AnamnesisField encontrado para este profissional. '
                'Execute seed_anamnesis primeiro.'
            )

        clients = Client.objects.filter(professional=professional)
        self.stdout.write(f'Clientes a migrar: {clients.count()}')

        total_created = 0
        total_skipped = 0
        total_empty = 0

        def upsert_response(client, anamnesis_field, value):
            nonlocal total_created, total_skipped

            if dry_run:
                self.stdout.write(
                    f'  [dry-run] {client} | {anamnesis_field.label}: {value[:60]}'
                )
                total_created += 1
                return

            _, created = AnamnesisResponse.objects.get_or_create(
                client=client,
                field=anamnesis_field,
                defaults={
                    'field_label_snap': anamnesis_field.label,
                    'value': value,
                },
            )
            if created:
                total_created += 1
            else:
                total_skipped += 1

        with transaction.atomic():
            for client in clients:
                for legacy_field, code in LEGACY_FIELD_MAP:
                    raw_value = getattr(client, legacy_field, None)

                    if raw_value is None or raw_value == '':
                        total_empty += 1
                        continue

                    value = str(raw_value).strip()
                    if not value:
                        total_empty += 1
                        continue

                    anamnesis_field = field_by_code.get(code)
                    if not anamnesis_field:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ! Campo "{code}" não encontrado no seed — pulando'
                            )
                        )
                        total_skipped += 1
                        continue

                    upsert_response(client, anamnesis_field, value)

                for legacy_field, base_code, detail_code in DETAIL_FIELD_MAP:
                    raw_value = getattr(client, legacy_field, None)
                    answer_value, detail_value = normalize_yes_no_with_detail(raw_value)
                    if answer_value is None:
                        total_empty += 1
                        continue

                    parent_field = field_by_code.get(base_code)
                    if not parent_field:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ! Campo "{base_code}" não encontrado no seed — pulando'
                            )
                        )
                        total_skipped += 1
                        continue

                    upsert_response(client, parent_field, answer_value)

                    if detail_value:
                        detail_field = field_by_code.get(detail_code)
                        if not detail_field:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  ! Campo "{detail_code}" não encontrado no seed — pulando detalhe'
                                )
                            )
                            total_skipped += 1
                            continue
                        upsert_response(client, detail_field, detail_value)

                if getattr(client, 'is_pregnant', None) is not None:
                    pregnancy_field = field_by_code.get(IS_PREGNANT_CODE)
                    if not pregnancy_field:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ! Campo "{IS_PREGNANT_CODE}" não encontrado no seed — pulando'
                            )
                        )
                        total_skipped += 1
                    else:
                        upsert_response(
                            client,
                            pregnancy_field,
                            'Sim' if client.is_pregnant else 'Não',
                        )
                else:
                    total_empty += 1

            if dry_run:
                transaction.set_rollback(True)

        verb = '[dry-run] seriam criadas' if dry_run else 'criadas'
        self.stdout.write(
            self.style.SUCCESS(
                f'\nConcluído: {total_created} respostas {verb}, '
                f'{total_skipped} já existiam/puladas, '
                f'{total_empty} campos vazios ignorados.'
            )
        )
