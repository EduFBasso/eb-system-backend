from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.expressions import RawSQL

from apps.anamnesis.models import AnamneseBase, AnamnesePodologia
from apps.clients.models import Client
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership


CLIENT_FIELDS = [
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

BASE_FIELDS = [
    'takes_medication',
    'had_surgery',
    'is_pregnant',
    'pain_sensitivity',
    'clinical_history',
    'sport_activity',
    'academic_activity',
]

PODO_FIELDS = [
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


def normalize_phone_digits(phone: Any) -> str | None:
    if not phone:
        return None
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    return digits or None


def normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)

    txt = str(value).strip().lower()
    if txt in {'1', 'true', 't', 'sim', 'yes', 'y'}:
        return True
    if txt in {'0', 'false', 'f', 'nao', 'não', 'no', 'n', ''}:
        return False
    return None


class Command(BaseCommand):
    help = (
        'Importa carga JSON no formato aninhado de podologia para PostgreSQL, '
        'forçando tenant/professional informados por ID.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default='.temp/carga_podologa.json',
            help='Caminho do JSON de entrada. Padrão: .temp/carga_podologa.json',
        )
        parser.add_argument(
            '--tenant',
            type=int,
            required=True,
            help='ID do Tenant destino',
        )
        parser.add_argument(
            '--professional',
            type=int,
            required=True,
            help='ID do Professional destino',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limite de registros para importar (0=todos)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula sem gravar no banco',
        )

    def handle(self, *args, **options): # type: ignore
        file_path = Path(str(options['file'])).expanduser().resolve()
        tenant_id = int(options['tenant'])
        professional_id = int(options['professional'])
        limit = int(options['limit'] or 0)
        dry_run = bool(options['dry_run'])

        if not file_path.exists() or not file_path.is_file():
            raise CommandError(f'Arquivo JSON não encontrado: {file_path}')

        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f'Tenant {tenant_id} não encontrado.') from exc

        try:
            professional = Professional.objects.get(pk=professional_id)
        except Professional.DoesNotExist as exc:
            raise CommandError(f'Professional {professional_id} não encontrado.') from exc

        has_membership = TenantMembership.objects.filter(
            tenant=tenant,
            professional=professional,
            is_active=True,
        ).exists()
        if not has_membership:
            self.stdout.write(self.style.WARNING(
                'Aviso: professional não possui membership ativa neste tenant. '
                'A importação ainda seguirá com os IDs informados.'
            ))

        with file_path.open('r', encoding='utf-8') as f:
            payload = json.load(f)

        if not isinstance(payload, list):
            raise CommandError('JSON inválido: a raiz deve ser uma lista de registros.')

        if limit > 0:
            payload = payload[:limit]

        created = 0
        updated = 0
        skipped = 0

        @transaction.atomic
        def run_import() -> None:
            nonlocal created, updated, skipped

            for index, item in enumerate(payload, start=1):
                if not isinstance(item, dict):
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f'Registro {index}: ignorado (não é objeto).'))
                    continue

                client_data = {field: item.get(field) for field in CLIENT_FIELDS}
                phone = normalize_phone_digits(client_data.get('phone'))
                email = str(client_data.get('email') or '').strip().lower() or None

                if not client_data.get('first_name') or not phone:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(
                        f'Registro {index}: ignorado (first_name e/ou phone ausente).'
                    ))
                    continue

                client_data['phone'] = phone
                client_data['email'] = email

                existing = self._find_existing_client(phone=phone, email=email)

                if existing:
                    for key, value in client_data.items():
                        setattr(existing, key, value)
                    existing.tenant = tenant
                    existing.professional = professional
                    existing.save()
                    client_obj = existing
                    updated += 1
                else:
                    client_obj = Client.objects.create(
                        tenant=tenant,
                        professional=professional,
                        **client_data,
                    )
                    created += 1

                base_payload = item.get('anamnese_base') or {}
                podo_payload = item.get('anamnese_podologia') or {}

                if not isinstance(base_payload, dict):
                    base_payload = {}
                if not isinstance(podo_payload, dict):
                    podo_payload = {}

                base_data = {key: base_payload.get(key) for key in BASE_FIELDS}
                base_data['is_pregnant'] = normalize_bool(base_data.get('is_pregnant'))

                podo_data = {key: podo_payload.get(key) for key in PODO_FIELDS}

                AnamneseBase.objects.update_or_create(
                    client=client_obj,
                    tenant=tenant,
                    professional=professional,
                    defaults=base_data,
                )

                AnamnesePodologia.objects.update_or_create(
                    client=client_obj,
                    tenant=tenant,
                    professional=professional,
                    defaults=podo_data,
                )

            if dry_run:
                transaction.set_rollback(True)

        run_import()

        mode = 'DRY-RUN' if dry_run else 'EXECUÇÃO'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: criados={created}, atualizados={updated}, ignorados={skipped}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Fonte: {file_path}'
        ))

    def _find_existing_client(self, phone: str | None, email: str | None) -> Client | None:
        if phone:
            exact = Client.objects.filter(phone=phone).first()
            if exact:
                return exact

            # Garante match com constraint de unicidade por dígitos (regexp_replace).
            by_digits = (
                Client.objects.annotate(
                    phone_digits=RawSQL(
                        "regexp_replace(phone::text, '[^0-9]', '', 'g')",
                        [],
                    )
                )
                .filter(phone_digits=phone)
                .first()
            )
            if by_digits:
                return by_digits

        if email:
            return Client.objects.filter(email=email).first()

        return None
