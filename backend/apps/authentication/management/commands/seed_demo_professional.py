import math
from datetime import timedelta, datetime
from typing import Optional

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from apps.clinic.models.clients import Client
from apps.authentication.models import Professional
from apps.clinic.models.agenda import Appointment


class Command(BaseCommand):
    help = "Cria um profissional de demonstração isolado, popula clientes sintéticos e agendamentos sequenciais."

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='E-mail do novo profissional (ou existente)')
        parser.add_argument('--password', default='demo123', help='Senha (caso crie)')
        parser.add_argument('--first-name', default='Demo', help='Primeiro nome')
        parser.add_argument('--last-name', default='Prof', help='Sobrenome')
        parser.add_argument('--clients', type=int, default=15, help='Quantidade de clientes a gerar')
        parser.add_argument('--appointments', type=int, default=10, help='Quantidade de agendamentos a gerar')
        parser.add_argument('--slot-minutes', type=int, default=45, help='Duração base de cada agendamento (min)')
        parser.add_argument('--start', help='Data/hora inicial (ISO). Default: próxima hora cheia local.')
        parser.add_argument('--dry-run', action='store_true', help='Simula sem gravar')

    @transaction.atomic
    def handle(self, *args, **options):
        email: str = options['email'].strip().lower()
        password: str = options['password']
        clients_qtd: int = options['clients']
        appt_qtd: int = options['appointments']
        slot_minutes: int = options['slot_minutes']
        start_iso: Optional[str] = options.get('start')
        dry_run: bool = options['dry_run']

        # 1) Profissional
        prof = Professional.objects.filter(email=email).first()
        created_prof = False
        if not prof:
            prof = Professional.objects.create_user( # type: ignore
                email=email,
                password=password,
                first_name=options['first_name'],
                last_name=options['last_name'],
            )
            created_prof = True

        self.stdout.write(self.style.SUCCESS(
            f"Profissional: {prof.email} (id={prof.id}) {'[CRIADO]' if created_prof else '[EXISTENTE]'}" # type: ignore
        ))

        # 2) Clientes sintéticos (não recria se já existem suficientes)
        existing_clients = prof.clients.count() # type: ignore
        to_create = max(0, clients_qtd - existing_clients)
        created_clients = []
        base_phone_prefix = '1198888'
        i = 0
        while to_create > 0 and not dry_run:
            phone_suffix = f"{existing_clients + i:03d}"  # garante 3 dígitos
            phone = base_phone_prefix + phone_suffix
            cli = Client.objects.create(
                professional=prof,
                first_name=f'Cliente{existing_clients + i + 1}',
                last_name='Demo',
                phone=phone,
            )
            created_clients.append(cli)
            i += 1
            to_create -= 1

        self.stdout.write(self.style.NOTICE(
            f"Clientes existentes: {existing_clients} | Novos criados: {len(created_clients)}"
        ))

        # 3) Agendamentos
        if start_iso:
            try:
                base_start = datetime.fromisoformat(start_iso)
                if base_start.tzinfo is None:
                    # assume timezone local (convert to aware)
                    base_start = timezone.make_aware(base_start, timezone.get_current_timezone())
            except Exception:
                raise SystemExit("Formato inválido em --start. Use ISO ex: 2025-09-12T08:00")
        else:
            now = timezone.localtime()
            base_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        appts_existing = Appointment.objects.filter(professional=prof).count()
        appts_to_create = max(0, appt_qtd - appts_existing)
        created_appts = []
        clients_cycle = list(prof.clients.order_by('id')[:max(1, clients_qtd)]) # type: ignore
        if not clients_cycle:
            self.stdout.write(self.style.WARNING('Nenhum cliente disponível para criar agendamentos.'))
        else:
            for n in range(appts_to_create):
                start_at = base_start + timedelta(minutes=slot_minutes * n)
                end_at = start_at + timedelta(minutes=slot_minutes)
                client = clients_cycle[n % len(clients_cycle)]
                if dry_run:
                    created_appts.append({'client': client.id, 'start': start_at, 'end': end_at})
                else:
                    appt = Appointment.objects.create(
                        professional=prof,
                        client=client,
                        title=f'Sessão {n+1}',
                        visit_type=Appointment.VisitType.AVALIACAO,
                        start_at=start_at,
                        end_at=end_at,
                    )
                    created_appts.append(appt)

        self.stdout.write(self.style.NOTICE(
            f"Agendamentos existentes: {appts_existing} | Novos criados: {len(created_appts)}"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run concluído (nada gravado).'))
        else:
            self.stdout.write(self.style.SUCCESS('Seed concluído.'))
            if created_prof:
                self.stdout.write(self.style.SUCCESS(f"Login: {prof.email} / Senha: {password}"))
