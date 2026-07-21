#!/usr/bin/env python3
"""Seed common anamnesis fields for all active professionals.

Usage:
  cd backend
  ./.venv/bin/python scripts/seed_common_anamnesis_fields.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import django


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clinic_project.settings")
django.setup()

from django.db import transaction

from apps.anamnesis.models import AnamnesisField
from apps.register.models import Professional


@dataclass(frozen=True)
class FieldSpec:
    code: str
    label: str
    field_type: str
    order: int
    sector: str = "Histórico"
    sector_order: int = 0
    options: list[str] | None = None
    placeholder: str = ""
    depends_on_code: str | None = None
    show_when_value: str = ""


COMMON_FIELDS: list[FieldSpec] = [
    FieldSpec(
        code="peso",
        label="Peso aproximado",
        field_type="text",
        order=10,
        placeholder="Ex.: 72 kg",
    ),
    FieldSpec(
        code="altura",
        label="Altura aproximada",
        field_type="text",
        order=20,
        placeholder="Ex.: 1,68 m",
    ),
    FieldSpec(
        code="pratica_esportes",
        label="Pratica esportes ou faz academia?",
        field_type="radio",
        options=["Sim", "Não"],
        order=30,
    ),
    FieldSpec(
        code="qual_esporte",
        label="Qual modalidade e frequência?",
        field_type="text",
        placeholder="Ex.: corrida 3x por semana",
        order=40,
        depends_on_code="pratica_esportes",
        show_when_value="Sim",
    ),
    FieldSpec(
        code="historico_doencas",
        label="Possui histórico de doenças principais?",
        field_type="radio",
        options=["Não", "Diabetes", "Hipertensão", "Cardiopatia", "Alergias", "Outros"],
        order=50,
    ),
    FieldSpec(
        code="outras_doencas",
        label="Descreva outras comorbidades ou condições:",
        field_type="text",
        placeholder="Ex.: hipotireoidismo, asma, etc.",
        order=60,
        depends_on_code="historico_doencas",
        show_when_value="Outros",
    ),
    FieldSpec(
        code="fez_cirurgia",
        label="Já realizou alguma cirurgia?",
        field_type="radio",
        options=["Sim", "Não"],
        order=70,
    ),
    FieldSpec(
        code="quais_cirurgias",
        label="Quais cirurgias e há quanto tempo?",
        field_type="text",
        placeholder="Ex.: apendicectomia há 5 anos",
        order=80,
        depends_on_code="fez_cirurgia",
        show_when_value="Sim",
    ),
    FieldSpec(
        code="toma_medicacao",
        label="Toma alguma medicação de uso contínuo?",
        field_type="radio",
        options=["Sim", "Não"],
        order=90,
    ),
    FieldSpec(
        code="quais_medicacoes",
        label="Quais medicações e dosagens?",
        field_type="textarea",
        placeholder="Ex.: losartana 50 mg/dia",
        order=100,
        depends_on_code="toma_medicacao",
        show_when_value="Sim",
    ),
]


@transaction.atomic
def seed_for_professional(professional: Professional) -> tuple[int, int]:
    by_code: dict[str, AnamnesisField] = {}
    created = 0
    updated = 0

    for spec in COMMON_FIELDS:
        field, was_created = AnamnesisField.objects.update_or_create(
            professional=professional,
            code=spec.code,
            defaults={
                "sector": spec.sector,
                "sector_order": spec.sector_order,
                "label": spec.label,
                "field_type": spec.field_type,
                "options": spec.options,
                "placeholder": spec.placeholder,
                "order": spec.order,
                "show_when_value": spec.show_when_value,
                "is_active": True,
            },
        )
        by_code[spec.code] = field
        if was_created:
            created += 1
        else:
            updated += 1

    for spec in COMMON_FIELDS:
        field = by_code[spec.code]
        parent = by_code.get(spec.depends_on_code) if spec.depends_on_code else None
        if field.depends_on_id != (parent.id if parent else None):
            field.depends_on = parent
            field.save(update_fields=["depends_on"])

    return created, updated


def main() -> None:
    professionals = Professional.objects.filter(is_active=True).order_by("id")
    total_created = 0
    total_updated = 0

    print(f"Profissionais ativos: {professionals.count()}")
    for professional in professionals:
        created, updated = seed_for_professional(professional)
        total_created += created
        total_updated += updated
        print(
            f"- {professional.id} {professional.email}: created={created} updated={updated}"
        )

    print(
        f"Seed concluído. Campos criados={total_created}, atualizados={total_updated}."
    )


if __name__ == "__main__":
    main()
