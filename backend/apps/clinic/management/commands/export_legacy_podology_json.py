from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


COMMON_FIELDS = [
    'first_name',
    'last_name',
    'email',
    'phone',
    'rg',
    'document_type',
    'document_number',
    'sex',
    'marital_status',
    'nationality',
    'profession',
    'address',
    'neighborhood',
    'city',
    'state',
    'postal_code',
    'date_of_birth',
    'address_number',
    'address_complement',
]

ANAMNESE_BASE_FIELDS = [
    'takes_medication',
    'had_surgery',
    'is_pregnant',
    'pain_sensitivity',
    'clinical_history',
    'sport_activity',
    'academic_activity',
]

ANAMNESE_PODOLOGIA_FIELDS = [
    'footwear_used',
    'sock_used',
    'plantar_view_left',
    'plantar_view_right',
    'dermatological_pathologies_left',
    'dermatological_pathologies_right',
    'nail_changes_left',
    'nail_changes_right',
    'deformities_left',
    'deformities_right',
    'sensitivity_test',
    'other_procedures',
]


class Command(BaseCommand):
    help = (
        'Exporta registros de clientes legados do SQLite para JSON no formato '
        'aninhado esperado pela nova API (client + anamnese_base + anamnese_podologia).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sqlite',
            default='db.sqlite3',
            help='Caminho do banco SQLite de origem. Padrão: db.sqlite3',
        )
        parser.add_argument(
            '--out',
            default='carga_podologa.json',
            help='Arquivo JSON de saída. Padrão: carga_podologa.json',
        )
        parser.add_argument(
            '--table',
            default='',
            help='Nome da tabela de origem (opcional). Se omitido, autodetecta.',
        )

    def handle(self, *args, **options): # type: ignore
        sqlite_path = Path(str(options['sqlite'])).expanduser().resolve()
        out_path = Path(str(options['out'])).expanduser().resolve()
        forced_table = str(options.get('table') or '').strip()

        if not sqlite_path.exists() or not sqlite_path.is_file():
            raise CommandError(f'Arquivo SQLite não encontrado: {sqlite_path}')

        with sqlite3.connect(str(sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row

            table_name = forced_table or self._detect_client_table(conn)
            if not table_name:
                raise CommandError(
                    'Não foi possível detectar tabela de clientes no SQLite. '
                    'Use --table para informar manualmente.'
                )

            rows = conn.execute(f'SELECT * FROM "{table_name}"').fetchall()
            payload = [self._row_to_payload(row) for row in rows]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open('w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(f'Tabela origem: {table_name}'))
        self.stdout.write(self.style.SUCCESS(f'Registros exportados: {len(payload)}'))
        self.stdout.write(self.style.SUCCESS(f'Arquivo gerado: {out_path}'))

    def _detect_client_table(self, conn: sqlite3.Connection) -> str:
        candidates = [
            'register_client',
            'clients_client',
            'client',
        ]

        available = {
            str(row['name'])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        for name in candidates:
            if name in available:
                return name

        best_match = ''
        best_score = -1

        for table in sorted(available):
            cols = self._table_columns(conn, table)
            score = 0
            if 'first_name' in cols and 'last_name' in cols:
                score += 2
            if 'phone' in cols:
                score += 1
            if 'footwear_used' in cols:
                score += 2
            if 'clinical_history' in cols:
                score += 1

            if score > best_score:
                best_score = score
                best_match = table

        return best_match if best_score > 0 else ''

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        return {
            str(row['name'])
            for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        }

    def _row_to_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        row_dict = dict(row)

        client_data = {field: row_dict.get(field) for field in COMMON_FIELDS}

        anamnese_base = {
            field: self._normalize_value(field, row_dict.get(field))
            for field in ANAMNESE_BASE_FIELDS
        }
        anamnese_podologia = {
            field: self._normalize_value(field, row_dict.get(field))
            for field in ANAMNESE_PODOLOGIA_FIELDS
        }

        payload = {
            **client_data,
            'anamnese_base': anamnese_base,
            'anamnese_podologia': anamnese_podologia,
        }

        legacy_id = row_dict.get('id')
        if legacy_id is not None:
            payload['_legacy_client_id'] = legacy_id

        return payload

    def _normalize_value(self, field_name: str, value: Any) -> Any:
        if value is None:
            return None

        if field_name == 'is_pregnant':
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return bool(value)

            normalized = str(value).strip().lower()
            if normalized in {'1', 'true', 't', 'sim', 'yes', 'y'}:
                return True
            if normalized in {'0', 'false', 'f', 'nao', 'não', 'no', 'n', ''}:
                return False
            return None

        return value
