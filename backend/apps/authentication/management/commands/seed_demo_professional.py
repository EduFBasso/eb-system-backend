# backend/apps/authentication/management/commands/seed_demo_professional.py
import math
from datetime import timedelta, datetime
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify
from django.db import transaction

from apps.clinic.models.clients import Client
from apps.authentication.models.register_models import Professional
from apps.authentication.models.tenancy_models import Tenant, TenantMembership
from apps.clinic.models.agenda import Appointment


class Command(BaseCommand):
    help = "Cria uma clínica (Tenant) de demonstração, associa um profissional e gera clientes e agendamentos sintéticos locais."

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='E-mail do profissional de testes (novo ou existente)')
        parser.add_argument('--password', default='demo123', help='Senha de acesso (padrão: demo123)')
        parser.add_argument('--first-name', default='Médica', help='Primeiro nome do profissional')
        parser.add_argument('--last-name', default='Demo', help='Sobrenome do profissional')
        parser.add_argument('--tenant-name', default='Clínica de Testes Local', dest='tenant_name', help='Nome da clínica de demonstração')
        parser.add_argument('--clients', type=int, default=15, help='Quantidade de clientes fictícios a gerar')
        parser.add_argument('--appointments', type=int, default=10, help='Quantidade de agendamentos fictícios a gerar')
        parser.add_argument('--slot-minutes', type=int, default=45, help='Duração da janela de cada consulta (minutos)')
        parser.add_argument('--start', help='Data/hora inicial formato ISO (ex: 2026-08-12T08:00). Default: próxima hora cheia.')
        parser.add_argument('--dry-run', action='store_true', help='Simula o processamento sem persistir dados no banco')

    @transaction.atomic
    def handle(self, *args, **options):
        email: str = options['email'].strip().lower()
        password: str = options['password']
        tenant_name: str = options['tenant_name'].strip()
        tenant_slug = slugify(tenant_name) or "clinica-demo-local"
        clients_qtd: int = options['clients']
        appt_qtd: int = options['appointments']
        slot_minutes: int = options['slot_minutes']
        start_iso: Optional[str] = options.get('start')
        dry_run: bool = options['dry_run']

        # 1) Garantia Estrutural: Criação/Recuperação da Clínica (Tenant)
        tenant, t_created = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                "name": tenant_name,
                "ecosystem": Tenant.Ecosystem.CLINIC,
                "capabilities": {"clinic": True, "podologia": True, "odonto": True},
                "is_active": True,
            }
        )
        self.stdout.write(self.style.SUCCESS(
            f"Clínica (Tenant): {tenant.name} ({tenant.slug}) {'[CRIADA]' if t_created else '[EXISTENTE]'}"
        ))

        # 2) Criação/Recuperação da Identidade do Profissional (Desativa TOTP por padrão no seed)
        prof = Professional.objects.filter(email=email).first()
        created_prof = False
        if not prof:
            prof = Professional.objects.create_user(
                email=email,
                password=password,
                first_name=options['first_name'],
                last_name=options['last_name'],
                totp_secret=""  # Garante login rápido local sem barreira de 2FA
            )
            created_prof = True

        self.stdout.write(self.style.SUCCESS(
            f"Profissional: {prof.email} (id={prof.id}) {'[CRIADO]' if created_prof else '[EXISTENTE]'}"
        ))

        # 3) Criação/Recuperação do Vínculo de Governança (TenantMembership)
        membership, m_created = TenantMembership.objects.get_or_create(
            tenant=tenant,
            professional=prof,
            defaults={
                "role": TenantMembership.Role.OWNER,
                "is_active": True
            }
        )

        # 4) Geração de Clientes Sintéticos Isolados por Tenant
        # Busca quantos clientes já existem associados a esta clínica específica
        existing_clients = Client.objects.filter(tenant=tenant).count()
        to_create = max(0, clients_qtd - existing_clients)
        created_clients = []
        base_phone_prefix = '1197777'
        
        i = 0
        while to_create > 0 and not dry_run:
            phone_suffix = f"{existing_clients + i:04d}"  # Garante preenchimento numérico sequencial único
            phone = base_phone_prefix + phone_suffix
            
            cli = Client.objects.create(
                tenant=tenant,  # [Multi-tenant] O cliente agora pertence obrigatoriamente à clínica
                first_name=f'Paciente Demo {existing_clients + i + 1}',
                last_name='Sintético',
                phone=phone,
                email=f"paciente_demo_{existing_clients + i + 1}@example.com"
            )
            created_clients.append(cli)
            i += 1
            to_create -= 1

        self.stdout.write(self.style.NOTICE(
            f"Clientes na Clínica: Existentes: {existing_clients} | Novos Injetados: {len(created_clients)}"
        ))

        # 5) Processamento Cronológico de Horários para a Agenda
        if start_iso:
            try:
                base_start = datetime.fromisoformat(start_iso)
                if base_start.tzinfo is None:
                    base_start = timezone.make_aware(base_start, timezone.get_current_timezone())
            except Exception:
                raise CommandError("Formato de data inválido em --start. Utilize o padrão ISO: YYYY-MM-DDTHH:MM")
        else:
            now = timezone.localtime()
            # Arredonda a semente para a próxima hora cheia do dia atual
            base_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        # Captura volumetria de agendamentos vigentes na clínica para este profissional
        appts_existing = Appointment.objects.filter(tenant=tenant, professional=prof).count()
        appts_to_create = max(0, appt_qtd - appts_existing)
        created_appts = []
        
        # Carrega o pool de clientes da clínica para distribuir sequencialmente na grade de horários
        clients_cycle = list(Client.objects.filter(tenant=tenant).order_by('id')[:max(1, clients_qtd)])
        
        if not clients_cycle:
            self.stdout.write(self.style.WARNING('Aviso: Nenhum cliente disponível no Tenant para armar a grade horária.'))
        else:
            for n in range(appts_to_create):
                start_at = base_start + timedelta(minutes=slot_minutes * n)
                end_at = start_at + timedelta(minutes=slot_minutes)
                client = clients_cycle[n % len(clients_cycle)]
                
                if dry_run:
                    created_appts.append({'client': client.id, 'start': start_at, 'end': end_at})
                else:
                    appt = Appointment.objects.create(
                        tenant=tenant,  # [Multi-tenant] Agendamento amarrado estritamente à clínica
                        professional=prof,
                        client=client,
                        title=f'Consulta Demonstrativa {n+1}',
                        # [Alinhamento de Enum] Ajustado para 'consulta' em conformidade com as regras limpas
                        visit_type=Appointment.VisitType.CONSULTA,
                        start_at=start_at,
                        end_at=end_at,
                    )
                    created_appts.append(appt)

        self.stdout.write(self.style.NOTICE(
            f"Agendamentos do Profissional: Existentes: {appts_existing} | Novos Injetados: {len(created_appts)}"
        ))

        # 6) Relatório Visual de Fechamento do Comando
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo Simulação (Dry-run) concluído com sucesso. Nada foi persistido.'))
        else:
            self.stdout.write(self.style.SUCCESS('🚀 Processo de Carga de Massa Fictícia (Seed) finalizado com sucesso.'))
            if created_prof:
                self.stdout.write(self.style.SUCCESS(f"   [Acesso Rápido de Testes] Usuário: {prof.email} | Senha: {password}"))
