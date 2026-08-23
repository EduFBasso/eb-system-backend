# backend/apps/authentication/management/commands/import_clients_csv.py
import csv
from typing import Optional, Dict, Any, List

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clinic.models.anamnesis import AnamneseBase, AnamnesePodologia
from apps.clinic.models.clients import Client
from apps.authentication.models.tenancy_models import Tenant
from apps.authentication.models.register_models import Professional


def normalize_phone_digits(phone: Optional[str]) -> Optional[str]:
    """Remove caracteres especiais e garante apenas dígitos para integridade de links públicos."""
    if not phone:
        return None
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    return digits or None


class Command(BaseCommand):
    help = (
        "Importa ou atualiza (upsert) clientes de um arquivo CSV associando-os a uma clínica (Tenant).\n"
        "Suporta o preenchimento automático das fichas de Anamnese Geral e Podologia em camadas."
    )

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Caminho do arquivo CSV a ser importado')
        parser.add_argument('--tenant-slug', required=True, help='Slug identificador da clínica (Tenant) de destino')
        parser.add_argument('--professional-email', help='E-mail do profissional responsável por assinar a anamnese (opcional)')
        parser.add_argument('--limit', type=int, default=0, help='Limite máximo de linhas a serem processadas (0=todas)')
        parser.add_argument('--dry-run', action='store_true', help='Executa em modo de simulação sem salvar nada no banco')

    def handle(self, *args, **options):
        file_path: str = options['file']
        tenant_slug: str = options['tenant_slug'].strip().lower()
        target_email: Optional[str] = options.get('professional_email')
        limit: int = options.get('limit') or 0
        dry_run: bool = bool(options.get('dry_run'))

        # [Garantia Multi-tenant] Localiza a clínica de destino obrigatória
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            raise CommandError(f"Erro: A clínica/empresa com o slug '{tenant_slug}' não foi encontrada.")

        # Localiza o profissional que assinará o prontuário base (se fornecido)
        professional = None
        if target_email:
            professional = Professional.objects.filter(email=target_email, is_active=True).first()
            if not professional:
                raise CommandError(f"Profissional com o e-mail '{target_email}' não foi encontrado ou está inativo.")
        else:
            # Fallback para o primeiro profissional cadastrado na clínica caso não seja informado
            membership = tenant.memberships.select_related('professional').filter(is_active=True).first()
            if membership:
                professional = membership.professional

        self.stdout.write(self.style.NOTICE(f"Iniciando importação de dados para a clínica: {tenant.name}"))
        if professional:
            self.stdout.write(self.style.NOTICE(f"Profissional associado às novas anamneses: {professional.email}"))

        # Efetua a leitura segura do CSV
        rows: List[Dict[str, Any]] = []
        try:
            with open(file_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Validação de cabeçalho
                expected = {
                    'first_name', 'last_name', 'email', 'phone', 'address', 'neighborhood', 'city', 'state'
                }
                header = set(reader.fieldnames or [])
                missing = expected - header
                if missing:
                    self.stdout.write(self.style.WARNING(
                        f"Aviso: Colunas obrigatórias ausentes no cabeçalho do CSV: {', '.join(sorted(missing))}. "
                        f"O sistema prosseguirá tentando mapear os dados existentes."
                    ))
                
                for row in reader:
                    rows.append(row)
                    if limit and len(rows) >= limit:
                        break
        except FileNotFoundError:
            raise CommandError(f"Arquivo CSV não encontrado no caminho indicado: {file_path}")

        self.stdout.write(self.style.NOTICE(f"Total de linhas carregadas do arquivo: {len(rows)}"))

        created = 0
        updated = 0
        skipped = 0

        def parse_bool(value: Optional[str]) -> Optional[bool]:
            if value is None:
                return None
            s = str(value).strip().lower()
            if s in {'true', '1', 'yes', 'y', 'sim'}:
                return True
            if s in {'false', '0', 'no', 'n', 'nao', 'não'}:
                return False
            return None

        @transaction.atomic
        def import_batch(items: List[Dict[str, Any]]):
            nonlocal created, updated, skipped
            for item in items:
                first_name = (item.get('first_name') or '').strip()
                last_name = (item.get('last_name') or '').strip()
                email_remote = (item.get('email') or '').strip().lower() or None
                phone_digits = normalize_phone_digits(item.get('phone'))
                address = (item.get('address') or None) or None
                neighborhood = (item.get('neighborhood') or None) or None
                city = (item.get('city') or None) or None
                state = (item.get('state') or None) or None

                # Atributos opcionais da entidade cliente
                profession = (item.get('profession') or None) or None
                postal_code = (item.get('postal_code') or None) or None

                # Separação de payloads seguindo os princípios de Responsabilidade Única (SRP)
                base_payload = {
                    'takes_medication': (item.get('takes_medication') or None) or None,
                    'had_surgery': (item.get('had_surgery') or None) or None,
                    'is_pregnant': parse_bool(item.get('is_pregnant')),
                    'pain_sensitivity': (item.get('pain_sensitivity') or None) or None,
                    'clinical_history': (item.get('clinical_history') or None) or None,
                    'sport_activity': (item.get('sport_activity') or None) or None,
                    'academic_activity': (item.get('academic_activity') or None) or None,
                }
                podologia_payload = {
                    'footwear_used': (item.get('footwear_used') or None) or None,
                    'sock_used': (item.get('sock_used') or None) or None,
                    'plantar_view_left': (item.get('plantar_view_left') or None) or None,
                    'plantar_view_right': (item.get('plantar_view_right') or None) or None,
                    'dermatological_pathologies_left': (item.get('dermatological_pathologies_left') or None) or None,
                    'dermatological_pathologies_right': (item.get('dermatological_pathologies_right') or None) or None,
                    'nail_changes_left': (item.get('nail_changes_left') or None) or None,
                    'nail_changes_right': (item.get('nail_changes_right') or None) or None,
                    'deformities_left': (item.get('deformities_left') or None) or None,
                    'deformities_right': (item.get('deformities_right') or None) or None,
                    'sensitivity_test': (item.get('sensitivity_test') or None) or None,
                    'other_procedures': (item.get('other_procedures') or None) or None,
                }

                # Ignora linhas complementares corrompidas ou sem dados de contato mínimos
                if not first_name and not phone_digits:
                    skipped += 1
                    continue

                # [Segurança Multi-tenant] A busca de unicidade ocorre estritamente dentro da mesma clínica
                existing = None
                if phone_digits:
                    existing = Client.objects.filter(tenant=tenant, phone=phone_digits).first()
                if not existing and email_remote:
                    existing = Client.objects.filter(tenant=tenant, email=email_remote).first()

                if existing:
                    changed = False
                    updates = {
                        'first_name': first_name or existing.first_name,
                        'last_name': last_name or existing.last_name,
                        'email': email_remote or existing.email,
                        'address': address if address is not None else existing.address,
                        'neighborhood': neighborhood if neighborhood is not None else existing.neighborhood,
                        'city': city if city is not None else existing.city,
                        'state': state if state is not None else existing.state,
                        'profession': profession if profession is not None else existing.profession,
                        'postal_code': postal_code if postal_code is not None else existing.postal_code,
                    }
                    for field, value in updates.items():
                        if getattr(existing, field) != value:
                            setattr(existing, field, value)
                            changed = True
                            
                    if changed and not dry_run:
                        existing.save()

                    if not dry_run:
                        base_values = {k: v for k, v in base_payload.items() if v is not None}
                        # Executa o upsert do cabeçalho clínico geral (AnamneseBase)
                        anamnese_base, _ = AnamneseBase.objects.update_or_create(
                            client=existing,
                            tenant=tenant,
                            defaults={
                                **base_values,
                                'professional': professional  # Injeta se houver profissional assinado
                            },
                        )
                        
                        podologia_values = {k: v for k, v in podologia_payload.items() if v is not None}
                        if podologia_values:
                            # [SOLID - Open/Closed Principle] Vincula a extensão de podologia à Anamnese Geral
                            AnamnesePodologia.objects.update_or_create(
                                anamnese_base=anamnese_base,
                                defaults={
                                    **podologia_values,
                                    'professional': professional
                                },
                            )
                    updated += 1 if changed else 0
                else:
                    if not phone_digits:
                        skipped += 1
                        continue
                        
                    if not dry_run:
                        # Criação inicial da entidade central do cliente vinculada à clínica (Tenant)
                        client = Client.objects.create(
                            tenant=tenant,
                            first_name=first_name or 'Cliente',
                            last_name=last_name or '',
                            email=email_remote,
                            phone=phone_digits,
                            address=address,
                            neighborhood=neighborhood,
                            city=city,
                            state=state,
                            profession=profession,
                            postal_code=postal_code,
                        )
                        
                        base_values = {k: v for k, v in base_payload.items() if v is not None}
                        # Instancia as tabelas dependentes em cascata de dados médicos
                        anamnese_base, _ = AnamneseBase.objects.update_or_create(
                            client=client,
                            tenant=tenant,
                            defaults={
                                **base_values,
                                'professional': professional
                            },
                        )
                        
                        podologia_values = {k: v for k, v in podologia_payload.items() if v is not None}
                        if podologia_values:
                            AnamnesePodologia.objects.update_or_create(
                                anamnese_base=anamnese_base,
                                defaults={
                                    **podologia_values,
                                    'professional': professional
                                },
                            )
                    created += 1

        # Dispara o processamento em lote sob transação atômica única de banco
        import_batch(rows)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Processamento Concluído (Modo Simulação: {dry_run}).\n"
            f"   Registros Criados: {created} | Atualizados: {updated} | Pulados/Erros: {skipped}"
        ))
