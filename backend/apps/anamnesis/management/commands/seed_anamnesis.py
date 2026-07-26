"""
Management command: seed_anamnesis

Populates AnamnesisField records for a specific professional from a seed file.
Idempotent: uses get_or_create, safe to run multiple times.

Usage:
    python manage.py seed_anamnesis --professional-email=podologa@clinica.com
    python manage.py seed_anamnesis --professional-email=podologa@clinica.com --seed=podologia_unhas
    python manage.py seed_anamnesis --professional-email=podologa@clinica.com --dry-run
"""

import importlib

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.anamnesis.models import AnamnesisField
from apps.register.models import Professional


def find_existing_field(professional, code, label, sector):
    field = AnamnesisField.objects.filter(
        professional=professional,
        code=code,
    ).first()
    if field:
        return field, False

    legacy_matches = list(
        AnamnesisField.objects.filter(
            professional=professional,
            label=label,
            sector=sector,
        ).order_by('id')
    )
    if len(legacy_matches) == 1:
        return legacy_matches[0], False

    return None, True


class Command(BaseCommand):
    help = 'Popula campos de anamnese para um profissional a partir de um seed file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--professional-email',
            required=True,
            help='E-mail do profissional que receberá os campos',
        )
        parser.add_argument(
            '--seed',
            default='podologia_unhas',
            help='Nome do módulo de seed em apps/anamnesis/seeds/ (default: podologia_unhas)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria criado sem salvar no banco',
        )

    def handle(self, *args, **options):
        email = options['professional_email']
        seed_name = options['seed']
        dry_run = options['dry_run']

        # Resolve professional
        try:
            professional = Professional.objects.get(email=email)
        except Professional.DoesNotExist:
            raise CommandError(f'Profissional com e-mail "{email}" não encontrado.')

        self.stdout.write(
            self.style.SUCCESS(
                f'Profissional: {professional.first_name} {professional.last_name} (id={professional.pk})'
            )
        )

        # Load seed module
        try:
            module = importlib.import_module(f'apps.anamnesis.seeds.{seed_name}')
        except ModuleNotFoundError:
            raise CommandError(
                f'Seed "{seed_name}" não encontrado em apps/anamnesis/seeds/. '
                f'Crie o arquivo apps/anamnesis/seeds/{seed_name}.py'
            )

        sectors = getattr(module, 'SECTORS', None)
        if not sectors:
            raise CommandError(f'Seed "{seed_name}" não contém a lista SECTORS.')

        created_count = 0
        existing_count = 0
        field_by_code: dict[str, AnamnesisField] = {}
        pending_dependencies: list[tuple[AnamnesisField, str | None, str]] = []

        for sector_block in sectors:
            sector = sector_block['sector']
            sector_order = sector_block['sector_order']

            for field_def in sector_block['fields']:
                code = field_def.get('code') or slugify(field_def['label']).replace('-', '_')
                if dry_run:
                    self.stdout.write(
                        f'  [dry-run] [{sector}] {field_def["label"]} '
                        f'({field_def["field_type"]})'
                    )
                    created_count += 1
                    continue

                obj, should_create = find_existing_field(
                    professional=professional,
                    code=code,
                    label=field_def['label'],
                    sector=sector,
                )

                created = False
                if should_create:
                    obj = AnamnesisField.objects.create(
                        professional=professional,
                        code=code,
                        label=field_def['label'],
                        sector=sector,
                        sector_order=sector_order,
                        field_type=field_def['field_type'],
                        selection_mode=field_def.get('selection_mode', 'single'),
                        options=field_def.get('options'),
                        placeholder=field_def.get('placeholder', ''),
                        show_when_value=field_def.get('show_when_value', ''),
                        order=field_def['order'],
                        is_active=True,
                    )
                    created = True

                field_by_code[code] = obj

                if created:
                    created_count += 1
                    self.stdout.write(f'  + [{sector}] {obj.label}')
                else:
                    updated_fields = []
                    if obj.code != code:
                        obj.code = code
                        updated_fields.append('code')
                    if obj.label != field_def['label']:
                        obj.label = field_def['label']
                        updated_fields.append('label')
                    if obj.sector != sector:
                        obj.sector = sector
                        updated_fields.append('sector')
                    if obj.options != field_def.get('options'):
                        obj.options = field_def.get('options')
                        updated_fields.append('options')
                    if obj.placeholder != field_def.get('placeholder', ''):
                        obj.placeholder = field_def.get('placeholder', '')
                        updated_fields.append('placeholder')
                    if obj.show_when_value != field_def.get('show_when_value', ''):
                        obj.show_when_value = field_def.get('show_when_value', '')
                        updated_fields.append('show_when_value')
                    if obj.field_type != field_def['field_type']:
                        obj.field_type = field_def['field_type']
                        updated_fields.append('field_type')
                    if obj.selection_mode != field_def.get('selection_mode', 'single'):
                        obj.selection_mode = field_def.get('selection_mode', 'single')
                        updated_fields.append('selection_mode')
                    if obj.order != field_def['order']:
                        obj.order = field_def['order']
                        updated_fields.append('order')
                    if obj.sector_order != sector_order:
                        obj.sector_order = sector_order
                        updated_fields.append('sector_order')
                    if updated_fields:
                        obj.save(update_fields=updated_fields)
                        self.stdout.write(f'  ↻ [{sector}] {obj.label} (atualizado: {", ".join(updated_fields)})')
                    else:
                        self.stdout.write(f'  ~ [{sector}] {obj.label} (já existia)')
                    existing_count += 1

                pending_dependencies.append(
                    (
                        obj,
                        field_def.get('depends_on'),
                        field_def.get('show_when_value', ''),
                    )
                )

        if not dry_run:
            for obj, depends_on_code, show_when_value in pending_dependencies:
                depends_on_field = (
                    field_by_code.get(depends_on_code) if depends_on_code else None
                )
                updated_fields = []
                if obj.depends_on_id != getattr(depends_on_field, 'id', None):
                    obj.depends_on = depends_on_field
                    updated_fields.append('depends_on')
                if obj.show_when_value != show_when_value:
                    obj.show_when_value = show_when_value
                    updated_fields.append('show_when_value')
                if updated_fields:
                    obj.save(update_fields=updated_fields)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\n[dry-run] {created_count} campos seriam criados.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nConcluído: {created_count} criados, {existing_count} já existiam.'
                )
            )
