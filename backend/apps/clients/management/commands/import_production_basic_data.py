from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clients.models import Client
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership


def _digits(value: Any) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _normalize_phone(value: Any) -> str | None:
    digits = _digits(value)
    return digits or None


def _normalize_cpf(raw_record: dict[str, Any]) -> str | None:
    direct = _digits(raw_record.get('cpf'))
    if len(direct) == 11:
        return direct

    document_number = _digits(raw_record.get('document_number'))
    if len(document_number) == 11:
        return document_number

    return None


def _normalize_postal_code(value: Any) -> str | None:
    digits = _digits(value)
    return digits or None


def _normalize_date(value: Any) -> str | None:
    if value in (None, ''):
        return None

    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None

    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        return text

    br_match = re.fullmatch(r'(\d{2})/(\d{2})/(\d{4})', text)
    if br_match:
        day, month, year = br_match.groups()
        return f'{year}-{month}-{day}'

    return None


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _iter_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        nested = payload.get('clients')
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]

    raise CommandError('Invalid JSON: root must be a list or an object with key "clients".')


class Command(BaseCommand):
    help = (
        'Purifies podology local JSON into basic personal/address data only and '
        'optionally imports into a target tenant/professional.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default='carga_podologa.json',
            help='Source JSON path (default: backend/carga_podologa.json).',
        )
        parser.add_argument(
            '--output',
            default='carga_producao_limpa.json',
            help='Output purified JSON path (default: backend/carga_producao_limpa.json).',
        )
        parser.add_argument(
            '--input-purified',
            default='',
            help='Optional purified JSON path used for import (skip raw source parsing).',
        )
        parser.add_argument(
            '--professional-id',
            type=int,
            default=2,
            help='Target professional id (default: 2, Regiane).',
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            default=0,
            help='Target tenant id. If omitted, resolves active membership for professional.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply import into database. Without this flag, command only exports JSON.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run import in transaction rollback mode (requires --apply).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Optional max number of source rows to process (0 = all).',
        )

    def handle(self, *args, **options):  # type: ignore[override]
        base_dir = Path.cwd()

        professional_id = int(options['professional_id'])
        tenant_id = int(options['tenant_id'] or 0)
        apply_import = bool(options['apply'])
        dry_run = bool(options['dry_run'])
        limit = int(options['limit'] or 0)

        professional = self._get_professional(professional_id)
        tenant = self._resolve_tenant(professional, tenant_id)

        source_path = (base_dir / str(options['source'])).resolve()
        output_path = (base_dir / str(options['output'])).resolve()
        purified_input_opt = str(options.get('input_purified') or '').strip()

        if purified_input_opt:
            purified_records = self._load_purified_file(
                (base_dir / purified_input_opt).resolve(),
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Loaded purified input with {len(purified_records)} records.',
                )
            )
        else:
            raw_records = self._load_source_records(source_path)
            purified_records, skipped = self._purify_records(
                raw_records,
                tenant_id=tenant.id,
                professional_id=professional.id,
                limit=limit,
            )
            self._write_output(output_path, purified_records)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Purified file generated: {output_path} | kept={len(purified_records)} skipped={skipped}',
                )
            )

        if not apply_import:
            self.stdout.write(self.style.WARNING('Export-only mode (use --apply to import).'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('Running import in dry-run mode.'))

        created, updated, ignored = self._import_records(
            records=purified_records,
            tenant=tenant,
            professional=professional,
            dry_run=dry_run,
        )

        mode = 'DRY-RUN' if dry_run else 'IMPORT'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: created={created} updated={updated} ignored={ignored}',
            )
        )

    def _get_professional(self, professional_id: int) -> Professional:
        try:
            return Professional.objects.get(pk=professional_id)
        except Professional.DoesNotExist as exc:
            raise CommandError(f'Professional id={professional_id} not found.') from exc

    def _resolve_tenant(self, professional: Professional, tenant_id: int) -> Tenant:
        if tenant_id:
            try:
                tenant = Tenant.objects.get(pk=tenant_id)
            except Tenant.DoesNotExist as exc:
                raise CommandError(f'Tenant id={tenant_id} not found.') from exc

            has_membership = TenantMembership.objects.filter(
                tenant=tenant,
                professional=professional,
                is_active=True,
            ).exists()
            if not has_membership:
                self.stdout.write(
                    self.style.WARNING(
                        'No active membership for selected tenant/professional. Import will still run with explicit IDs.',
                    )
                )
            return tenant

        membership = (
            TenantMembership.objects.select_related('tenant')
            .filter(professional=professional, is_active=True, tenant__is_active=True)
            .order_by('created_at', 'id')
            .first()
        )
        if membership is None:
            raise CommandError(
                'Cannot resolve tenant automatically. Provide --tenant-id explicitly.',
            )
        return membership.tenant

    def _load_source_records(self, source_path: Path) -> list[dict[str, Any]]:
        if not source_path.exists() or not source_path.is_file():
            raise CommandError(f'Source JSON not found: {source_path}')

        with source_path.open('r', encoding='utf-8') as source_file:
            payload = json.load(source_file)

        return _iter_records(payload)

    def _purify_records(
        self,
        raw_records: list[dict[str, Any]],
        *,
        tenant_id: int,
        professional_id: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        records = raw_records[:limit] if limit > 0 else raw_records

        purified: list[dict[str, Any]] = []
        skipped = 0

        for row in records:
            first_name = _as_text(row.get('first_name'))
            last_name = _as_text(row.get('last_name'))
            phone = _normalize_phone(row.get('phone'))

            if not first_name or not last_name or not phone:
                skipped += 1
                continue

            purified.append(
                {
                    'tenant_id': tenant_id,
                    'professional_id': professional_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone,
                    'cpf': _normalize_cpf(row),
                    'date_of_birth': _normalize_date(row.get('date_of_birth')),
                    'address': _as_text(row.get('address')),
                    'address_number': _as_text(row.get('address_number')),
                    'neighborhood': _as_text(row.get('neighborhood')),
                    'city': _as_text(row.get('city')),
                    'postal_code': _normalize_postal_code(row.get('postal_code')),
                }
            )

        return purified, skipped

    def _write_output(self, output_path: Path, records: list[dict[str, Any]]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as out_file:
            json.dump(records, out_file, ensure_ascii=False, indent=2)

    def _load_purified_file(self, file_path: Path) -> list[dict[str, Any]]:
        if not file_path.exists() or not file_path.is_file():
            raise CommandError(f'Purified input JSON not found: {file_path}')

        with file_path.open('r', encoding='utf-8') as input_file:
            payload = json.load(input_file)

        records = _iter_records(payload)
        # Keep only keys accepted by the importer.
        cleaned: list[dict[str, Any]] = []
        for row in records:
            cleaned.append(
                {
                    'first_name': _as_text(row.get('first_name')),
                    'last_name': _as_text(row.get('last_name')),
                    'phone': _normalize_phone(row.get('phone')),
                    'cpf': _normalize_cpf(row),
                    'date_of_birth': _normalize_date(row.get('date_of_birth')),
                    'address': _as_text(row.get('address')),
                    'address_number': _as_text(row.get('address_number')),
                    'neighborhood': _as_text(row.get('neighborhood')),
                    'city': _as_text(row.get('city')),
                    'postal_code': _normalize_postal_code(row.get('postal_code')),
                }
            )
        return cleaned

    def _import_records(
        self,
        *,
        records: list[dict[str, Any]],
        tenant: Tenant,
        professional: Professional,
        dry_run: bool,
    ) -> tuple[int, int, int]:
        created = 0
        updated = 0
        ignored = 0

        @transaction.atomic
        def _run() -> None:
            nonlocal created, updated, ignored

            for row in records:
                first_name = _as_text(row.get('first_name'))
                last_name = _as_text(row.get('last_name'))
                phone = _normalize_phone(row.get('phone'))

                if not first_name or not last_name or not phone:
                    ignored += 1
                    continue

                cpf = _normalize_cpf(row)
                defaults = {
                    'tenant': tenant,
                    'professional': professional,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone,
                    'document_type': 'cpf' if cpf else None,
                    'document_number': cpf,
                    'date_of_birth': _normalize_date(row.get('date_of_birth')),
                    'address': _as_text(row.get('address')),
                    'address_number': _as_text(row.get('address_number')),
                    'neighborhood': _as_text(row.get('neighborhood')),
                    'city': _as_text(row.get('city')),
                    'postal_code': _normalize_postal_code(row.get('postal_code')),
                }

                existing = Client.objects.filter(phone=phone).first()
                if existing:
                    for key, value in defaults.items():
                        setattr(existing, key, value)
                    existing.save()
                    updated += 1
                else:
                    Client.objects.create(**defaults)
                    created += 1

            if dry_run:
                transaction.set_rollback(True)

        _run()
        return created, updated, ignored