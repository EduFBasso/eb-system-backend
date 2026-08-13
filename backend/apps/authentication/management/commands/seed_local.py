# backend/apps/authentication/management/commands/seed_local.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from apps.clinic.models.clients import Client
from apps.authentication.models.register_models import Professional
from apps.authentication.models.tenancy_models import Tenant, TenantMembership


class Command(BaseCommand):
    help = "Gera massa de dados inicial rápida para o ambiente de desenvolvimento local (Tenant + Profissional + Clientes)"

    def add_arguments(self, parser):
        parser.add_argument('--email', default='dev@example.com')
        parser.add_argument('--password', default='dev123')
        parser.add_argument('--first', dest='first_name', default='Dev')
        parser.add_argument('--last', dest='last_name', default='User')
        parser.add_argument('--tenant-name', default='Clínica Desenvolvimento Local', dest='tenant_name')
        parser.add_argument('--clients', type=int, default=6)

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        password = options['password']
        num_clients = options['clients']
        first_name = options['first_name']
        last_name = options['last_name']
        tenant_name = options['tenant_name'].strip()
        tenant_slug = slugify(tenant_name) or "clinica-dev-local"

        # 1) [Garantia Multi-tenant] Criação da Clínica Local canônica
        tenant, t_created = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                'name': tenant_name,
                'ecosystem': Tenant.Ecosystem.CLINIC,
                'capabilities': {'clinic': True, 'podologia': True},
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Tenant pronto: {tenant.name} ({tenant.slug})"))

        # 2) Criação do Usuário de Desenvolvimento sem segredo TOTP ativo
        prof, created = Professional.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'register_number': 'DEV-000',
                'specialty': 'Podologia',
                'is_active': True,
                'totp_secret': '',  # Desativa explicitamente o segundo fator localmente
            }
        )
        
        # Garante a atualização ou injeção da senha de acesso legível de testes
        prof.set_password(password)
        prof.save(update_fields=['password'])
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"Professional dev criado: {email} / {password}"))
        else:
            self.stdout.write(self.style.WARNING(f"Professional já existente; senha redefinida: {email} / {password}"))

        # 3) Vinculação de Controle e Governança do usuário na clínica
        TenantMembership.objects.get_or_create(
            tenant=tenant,
            professional=prof,
            defaults={
                'role': TenantMembership.Role.OWNER,
                'is_active': True,
            }
        )

        # 4) Geração automatizada de clientes sintéticos locais pertencentes ao Tenant
        first_names = [
            'Ana', 'Bruno', 'Carla', 'Daniel', 'Eva', 'Felipe', 'Giovana', 'Henrique', 'Isabela', 'João'
        ]
        created_count = 0
        for i in range(num_clients):
            fn = first_names[i % len(first_names)]
            ln = f"Teste{i+1}"
            phone = f"+55119999{i:04d}"

            # A busca de duplicidade agora trava estritamente isolada na combinação (Tenant, Telefone)
            client, c_created = Client.objects.get_or_create(
                tenant=tenant,  # [Multi-tenant] Atribuído diretamente à clínica controladora
                phone=phone,
                defaults={
                    'first_name': fn,
                    'last_name': ln,
                    'city': 'São Paulo',
                    'state': 'SP',
                }
            )
            created_count += 1 if c_created else 0

        self.stdout.write(self.style.SUCCESS(f"Clientes locais prontos (criados: {created_count}, requisitados: {num_clients})."))
        self.stdout.write(self.style.SUCCESS("🚀 Seed de ambiente de desenvolvimento local concluído com sucesso total."))
