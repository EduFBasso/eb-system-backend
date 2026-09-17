from datetime import datetime, timedelta
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.authentication.models.register_models import Professional
from apps.authentication.models.tenancy_models import Tenant, TenantMembership
from apps.clinic.models.agenda import Appointment
from apps.clinic.models.clients import Client


class Command(BaseCommand):
    help = "Cria uma clínica (Tenant) de demonstração, associa um profissional e gera clientes e agendamentos sintéticos locais."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="E-mail do profissional de testes (novo ou existente)")
        parser.add_argument("--password", default="demo123", help="Senha de acesso (padrão: demo123)")
        parser.add_argument("--first-name", default="Médica", help="Primeiro nome do profissional")
        parser.add_argument("--last-name", default="Demo", help="Sobrenome do profissional")
        parser.add_argument("--tenant-name", default="Clínica de Testes Local", dest="tenant_name", help="Nome da clínica de demonstração")
        parser.add_argument("--specialty", choices=("odonto", "podologia"), default="podologia", help="Especialidade exclusiva da clínica de demonstração (padrão: podologia)")
        parser.add_argument("--clients", type=int, default=15, help="Quantidade de clientes fictícios a gerar")
        parser.add_argument("--appointments", type=int, default=10, help="Quantidade de agendamentos fictícios a gerar")
        parser.add_argument("--slot-minutes", type=int, default=45, help="Duração da janela de cada consulta (minutos)")
        parser.add_argument("--start", help="Data/hora inicial formato ISO (ex: 2026-08-12T08:00). Default: próxima hora cheia.")
        parser.add_argument("--dry-run", action="store_true", help="Simula o processamento sem persistir dados no banco")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        tenant_name = options["tenant_name"].strip()
        tenant_slug = slugify(tenant_name) or "clinica-demo-local"
        clients_quantity = options["clients"]
        appointments_quantity = options["appointments"]
        slot_minutes = options["slot_minutes"]
        start_iso: Optional[str] = options.get("start")
        dry_run = options["dry_run"]
        capabilities = {"clinic": True, options["specialty"]: True}

        tenant, tenant_created = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                "name": tenant_name,
                "ecosystem": Tenant.Ecosystem.CLINIC,
                "capabilities": capabilities,
                "is_active": True,
            },
        )
        if not tenant_created and tenant.capabilities != capabilities:
            tenant.capabilities = capabilities
            tenant.save(update_fields=["capabilities"])
        self.stdout.write(self.style.SUCCESS(
            f"Clínica (Tenant): {tenant.name} ({tenant.slug}) {'[CRIADA]' if tenant_created else '[EXISTENTE]'}"
        ))

        professional = Professional.objects.filter(email=email).first()
        professional_created = False
        if not professional:
            professional = Professional.objects.create_user(
                email=email,
                password=password,
                first_name=options["first_name"],
                last_name=options["last_name"],
            )
            professional_created = True
        self.stdout.write(self.style.SUCCESS(
            f"Profissional: {professional.email} (id={professional.id}) {'[CRIADO]' if professional_created else '[EXISTENTE]'}"
        ))

        TenantMembership.objects.get_or_create(
            tenant=tenant,
            professional=professional,
            defaults={"role": TenantMembership.Role.OWNER, "is_active": True},
        )

        existing_clients = Client.objects.filter(tenant=tenant).count()
        clients_to_create = max(0, clients_quantity - existing_clients)
        created_clients = []
        while clients_to_create > 0 and not dry_run:
            offset = existing_clients + len(created_clients)
            client = Client.objects.create(
                tenant=tenant,
                first_name=f"Paciente Demo {offset + 1}",
                last_name="Sintético",
                phone=f"1197777{offset:04d}",
                email=f"paciente_demo_{offset + 1}@example.com",
            )
            created_clients.append(client)
            clients_to_create -= 1

        self.stdout.write(self.style.NOTICE(
            f"Clientes na Clínica: Existentes: {existing_clients} | Novos Injetados: {len(created_clients)}"
        ))

        if start_iso:
            try:
                base_start = datetime.fromisoformat(start_iso)
                if base_start.tzinfo is None:
                    base_start = timezone.make_aware(base_start, timezone.get_current_timezone())
            except Exception:
                raise CommandError("Formato de data inválido em --start. Utilize o padrão ISO: YYYY-MM-DDTHH:MM")
        else:
            now = timezone.localtime()
            base_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        existing_appointments = Appointment.objects.filter(tenant=tenant, professional=professional).count()
        appointments_to_create = max(0, appointments_quantity - existing_appointments)
        created_appointments = []
        clients_cycle = list(Client.objects.filter(tenant=tenant).order_by("id")[:max(1, clients_quantity)])

        if not clients_cycle:
            self.stdout.write(self.style.WARNING("Aviso: Nenhum cliente disponível no Tenant para armar a grade horária."))
        else:
            for index in range(appointments_to_create):
                start_at = base_start + timedelta(minutes=slot_minutes * index)
                end_at = start_at + timedelta(minutes=slot_minutes)
                client = clients_cycle[index % len(clients_cycle)]
                if dry_run:
                    created_appointments.append({"client": client.id, "start": start_at, "end": end_at})
                else:
                    created_appointments.append(Appointment.objects.create(
                        tenant=tenant,
                        professional=professional,
                        client=client,
                        title=f"Consulta Demonstrativa {index + 1}",
                        visit_type=Appointment.VisitType.CONSULTA,
                        start_at=start_at,
                        end_at=end_at,
                    ))

        self.stdout.write(self.style.NOTICE(
            f"Agendamentos do Profissional: Existentes: {existing_appointments} | Novos Injetados: {len(created_appointments)}"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo Simulação (Dry-run) concluído com sucesso. Nada foi persistido."))
        else:
            self.stdout.write(self.style.SUCCESS("🚀 Processo de Carga de Massa Fictícia (Seed) finalizado com sucesso."))
            if professional_created:
                self.stdout.write(self.style.SUCCESS(
                    f"   [Acesso Rápido de Testes] Usuário: {professional.email} | Senha: {password}"
                ))
