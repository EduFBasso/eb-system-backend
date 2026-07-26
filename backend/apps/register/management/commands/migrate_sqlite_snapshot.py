from __future__ import annotations

import sqlite3
import re
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Iterable

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections, transaction
from django.db.models import (
    AutoField,
    BigAutoField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    PositiveBigIntegerField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    SmallIntegerField,
    TextField,
)


DEFAULT_APP_LABELS = [
    "register",
    "clients",
    "agenda",
    "inventory",
    "anamnesis",
    "reminders",
]
SOURCE_DB_ALIAS = "sqlite_source"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class Command(BaseCommand):
    help = (
        "Migra dados de um snapshot SQLite para o banco default (PostgreSQL) com dry-run por padrao."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            required=True,
            help="Caminho absoluto para o arquivo SQLite de origem.",
        )
        parser.add_argument(
            "--apps",
            default=",".join(DEFAULT_APP_LABELS),
            help=(
                "Lista de app labels separados por virgula para migrar. "
                f"Padrao: {','.join(DEFAULT_APP_LABELS)}"
            ),
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica a migracao. Sem esta flag, apenas simula (dry-run).",
        )
        parser.add_argument(
            "--truncate-target",
            action="store_true",
            help=(
                "Antes de importar, limpa as tabelas dos apps informados no banco de destino "
                "(TRUNCATE ... CASCADE para PostgreSQL)."
            ),
        )

    def handle(self, *args, **options):
        source = Path(str(options["source"])).expanduser().resolve()
        app_labels = self._parse_app_labels(str(options["apps"]))
        execute = bool(options["execute"])
        truncate_target = bool(options["truncate_target"])

        self._validate_source(source)
        self._validate_app_labels(app_labels)
        self._ensure_not_sqlite_default()

        migration_plan = self._build_migration_plan(source, app_labels)
        source_counts = Counter(
            {item["model_label"]: item["row_count"] for item in migration_plan}
        )
        target_counts = self._count_target(app_labels)

        self.stdout.write("Resumo da migracao SQLite -> default")
        self.stdout.write(f"- source: {source}")
        self.stdout.write(f"- apps: {', '.join(app_labels)}")
        self.stdout.write(f"- registros no source: {sum(source_counts.values())}")
        self.stdout.write(f"- registros no target: {sum(target_counts.values())}")

        self.stdout.write("\nTop modelos no source:")
        for model_label, count in source_counts.most_common(15):
            self.stdout.write(f"- {model_label}: {count}")

        missing_columns = [
            item
            for item in migration_plan
            if item["missing_columns"]
        ]
        if missing_columns:
            self.stdout.write("\nColunas ausentes no source (serao preenchidas com default quando possivel):")
            for item in missing_columns[:15]:
                cols = ", ".join(item["missing_columns"])
                self.stdout.write(f"- {item['model_label']}: {cols}")

        if not execute:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run concluido. Nada foi alterado. "
                    "Use --execute para aplicar e --truncate-target para limpar antes de importar."
                )
            )
            return

        if not truncate_target:
            raise CommandError(
                "Para execucao real, use tambem --truncate-target. "
                "Isso evita duplicacao/inconsistencia durante a carga."
            )

        with transaction.atomic():
            self._truncate_target_tables(app_labels)
            self._load_from_sqlite(source, migration_plan)
            self._reset_sequences(app_labels)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Migracao aplicada com sucesso."))
        self.stdout.write(
            self.style.SUCCESS(
                f"- registros importados: {sum(source_counts.values())}"
            )
        )

    def _parse_app_labels(self, raw: str) -> list[str]:
        labels = [p.strip() for p in raw.split(",") if p.strip()]
        if not labels:
            raise CommandError("Informe ao menos um app em --apps.")
        return labels

    def _validate_source(self, source: Path) -> None:
        if not source.exists():
            raise CommandError(f"Arquivo source nao encontrado: {source}")
        if not source.is_file():
            raise CommandError(f"Source invalido (nao e arquivo): {source}")

    def _validate_app_labels(self, app_labels: Iterable[str]) -> None:
        installed = {cfg.label for cfg in apps.get_app_configs()}
        unknown = [label for label in app_labels if label not in installed]
        if unknown:
            raise CommandError(
                f"Apps invalidos em --apps: {', '.join(unknown)}. "
                f"Instalados: {', '.join(sorted(installed))}"
            )

    def _ensure_not_sqlite_default(self) -> None:
        engine = settings.DATABASES["default"].get("ENGINE", "")
        if "postgresql" not in engine:
            raise CommandError(
                "Banco default atual nao e PostgreSQL. "
                "Configure o ambiente para apontar para o Postgres (Docker/Render) antes da migracao."
            )

    def _build_migration_plan(self, source: Path, app_labels: list[str]) -> list[dict]:
        source_tables = self._read_source_tables(source)
        ordered_models = self._topological_model_order(app_labels)
        plan: list[dict] = []

        for model in ordered_models:
            table = model._meta.db_table
            source_columns = source_tables.get(table)
            if source_columns is None:
                continue

            field_entries = []
            missing_columns = []
            for field in model._meta.concrete_fields:
                if field.column in source_columns:
                    field_entries.append(
                        {
                            "field": field,
                            "from_source": True,
                            "source_column": field.column,
                        }
                    )
                else:
                    field_entries.append(
                        {
                            "field": field,
                            "from_source": False,
                            "source_column": field.column,
                        }
                    )
                    missing_columns.append(field.column)

            row_count = self._source_row_count(source, table)
            plan.append(
                {
                    "model": model,
                    "model_label": f"{model._meta.app_label}.{model._meta.model_name}",
                    "table": table,
                    "field_entries": field_entries,
                    "missing_columns": missing_columns,
                    "row_count": row_count,
                }
            )

        if not plan:
            raise CommandError("Nenhum modelo/tabela elegivel encontrado no source.")

        return plan

    def _read_source_tables(self, source: Path) -> dict[str, set[str]]:
        tables: dict[str, set[str]] = {}
        with sqlite3.connect(str(source)) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for (table_name,) in rows:
                cols = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                tables[table_name] = {str(col[1]) for col in cols}
        return tables

    def _source_row_count(self, source: Path, table: str) -> int:
        with sqlite3.connect(str(source)) as conn:
            return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])

    def _topological_model_order(self, app_labels: list[str]) -> list[type]:
        models = [
            m
            for m in apps.get_models()
            if m._meta.app_label in app_labels and m._meta.managed and not m._meta.proxy
        ]
        model_set = set(models)
        deps: dict[type, set[type]] = {m: set() for m in models}

        for model in models:
            for field in model._meta.concrete_fields:
                if isinstance(field, ForeignKey):
                    dep = field.remote_field.model
                    if dep in model_set:
                        deps[model].add(dep)

        ordered: list[type] = []
        ready = [m for m, d in deps.items() if not d]
        while ready:
            m = ready.pop()
            ordered.append(m)
            for candidate, candidate_deps in deps.items():
                if m in candidate_deps:
                    candidate_deps.remove(m)
                    if not candidate_deps and candidate not in ordered and candidate not in ready:
                        ready.append(candidate)

        if len(ordered) != len(models):
            # Fallback deterministico caso exista ciclo.
            return sorted(models, key=lambda mm: mm._meta.db_table)

        return ordered

    def _count_target(self, app_labels: list[str]) -> Counter[str]:
        counts: Counter[str] = Counter()
        for model in apps.get_models():
            if model._meta.app_label not in app_labels:
                continue
            model_label = f"{model._meta.app_label}.{model._meta.model_name}"
            counts[model_label] = model.objects.count()
        return counts

    def _truncate_target_tables(self, app_labels: list[str]) -> None:
        table_names: list[str] = []
        for model in apps.get_models():
            if (
                model._meta.app_label not in app_labels
                or not model._meta.managed
                or model._meta.proxy
            ):
                continue
            table_names.append(model._meta.db_table)

        if not table_names:
            raise CommandError("Nenhuma tabela alvo encontrada para truncar.")

        quoted = ", ".join(connection.ops.quote_name(t) for t in sorted(set(table_names)))
        sql = f"TRUNCATE {quoted} RESTART IDENTITY CASCADE;"
        with connection.cursor() as cursor:
            cursor.execute(sql)

    def _load_from_sqlite(self, source: Path, migration_plan: list[dict]) -> None:
        with sqlite3.connect(str(source)) as src_conn:
            src_conn.row_factory = sqlite3.Row
            for item in migration_plan:
                model = item["model"]
                table = item["table"]
                source_fields = [
                    e for e in item["field_entries"] if e["from_source"]
                ]

                if source_fields:
                    source_cols_sql = ", ".join(
                        f'"{e["source_column"]}"' for e in source_fields
                    )
                    query = f'SELECT {source_cols_sql} FROM "{table}"'
                    rows = src_conn.execute(query).fetchall()
                else:
                    rows = []

                objects = []
                for row in rows:
                    kwargs = {}
                    for field_entry in item["field_entries"]:
                        field = field_entry["field"]
                        if field_entry["from_source"]:
                            kwargs[field.attname] = row[field_entry["source_column"]]
                        else:
                            kwargs[field.attname] = self._fallback_value(field)
                    objects.append(model(**kwargs))

                if objects:
                    model.objects.bulk_create(objects, batch_size=500)

                self.stdout.write(
                    f"- importado {item['model_label']}: {len(objects)}"
                )

    def _fallback_value(self, field):
        if field.has_default():
            default = field.get_default()
            return default() if callable(default) else default

        if field.null:
            return None

        if isinstance(field, (CharField, TextField)):
            return ""

        if isinstance(field, BooleanField):
            return False

        if isinstance(
            field,
            (
                IntegerField,
                PositiveIntegerField,
                PositiveSmallIntegerField,
                PositiveBigIntegerField,
                SmallIntegerField,
            ),
        ):
            return 0

        if isinstance(field, DateTimeField):
            return None

        if isinstance(field, (AutoField, BigAutoField)):
            return None

        raise CommandError(
            f"Sem valor para coluna ausente {field.model._meta.db_table}.{field.column}. "
            "Adicione default no model/migration ou ajuste o source."
        )

    def _reset_sequences(self, app_labels: list[str]) -> None:
        out = StringIO()
        call_command("sqlsequencereset", *app_labels, stdout=out, no_color=True)
        raw_sql = out.getvalue().strip()
        if not raw_sql:
            return

        statements = []
        for raw_line in raw_sql.splitlines():
            line = ANSI_RE.sub("", raw_line).strip()
            if not line:
                continue
            if line.upper() in {"BEGIN;", "COMMIT;"}:
                continue
            statements.append(line)

        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
