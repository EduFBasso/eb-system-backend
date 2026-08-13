# backend/apps/authentication/models/tenancy_models.py
from django.db import models


class Tenant(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Modela a entidade canônica do Inquilino (Tenant). Representa uma unidade corporativa 
    isolada no sistema, como uma Clínica de saúde ou uma Unidade de Padaria.
    """
    class Ecosystem(models.TextChoices):
        CLINIC = 'clinic', 'Unidade Clínica (Saúde/Estética)'
        BAKERY = 'bakery', 'Unidade Padaria (Alimentação/Varejo)'

    name = models.CharField("Nome da Empresa / Unidade", max_length=120)
    slug = models.SlugField(
        "Identificador na URL (Slug)", 
        max_length=140, 
        unique=True,
        help_text="Texto amigável usado na URL para identificar a clínica. Ex: 'clinica-arcaro'"
    )
    ecosystem = models.CharField(
        "Ecossistema / Tipo de Negócio",
        max_length=20,
        choices=Ecosystem.choices,
        default=Ecosystem.CLINIC,
    )
    
    # Campo dinâmico para ativar/desativar módulos extras via painel administrativo
    # Exemplo: {"modules": {"podologia": true, "odonto": false}}
    capabilities = models.JSONField(
        "Capacidades / Funcionalidades Ativas", 
        default=dict, 
        blank=True
    )
    
    is_active = models.BooleanField("Cadastro Ativo?", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'authentication'
        verbose_name = 'Empresa (Tenant)'
        verbose_name_plural = 'Empresas (Tenants)'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['ecosystem', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} [{self.get_ecosystem_display()}]"

    def has_capability(self, capability_name: str) -> bool:
        """
        Interpreta o JSONField de configurações para checar se a clínica 
        possui autorização para acessar um recurso específico.
        """
        capability_value = self.capabilities.get(capability_name)
        if isinstance(capability_value, bool):
            return capability_value

        modules = self.capabilities.get('modules')
        if isinstance(modules, dict):
            module_value = modules.get(capability_name)
            if isinstance(module_value, bool):
                return module_value

        return False


class TenantMembership(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Mecanismo central de controle de acesso (RBAC). 
    Define o vínculo de controle, dadas as permissões de um Profissional dentro de um Tenant específico.
    """
    class Role(models.TextChoices):
        OWNER = 'owner', 'Proprietário / Sócio Diretor'
        ADMIN = 'admin', 'Administrador da Unidade'
        MEMBER = 'member', 'Membro Operacional / Profissional de Saúde'

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name="Empresa / Clínica"
    )
    professional = models.ForeignKey(
        'authentication.Professional',
        on_delete=models.CASCADE,
        related_name='tenant_memberships',
        verbose_name="Profissional Vinculado"
    )
    role = models.CharField(
        "Nível de Permissão (Role)",
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    
    # Apelido de login rápido (ex: 'regiane') único estritamente dentro daquela clínica
    login_alias = models.CharField(
        "Apelido de Login Rápido", 
        max_length=60, 
        blank=True, 
        default='',
        help_text="Permite ao profissional autenticar-se usando um apelido curto em vez do e-mail."
    )
    is_active = models.BooleanField("Vínculo Habilitado?", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'authentication'
        verbose_name = 'Vínculo de Acesso (Membership)'
        verbose_name_plural = 'Vínculos de Acessos (Memberships)'
        
        # Garante que um profissional não possua dois papéis duplicados na mesma clínica
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'professional'],
                name='uniq_tenant_membership_professional_combination'
            ),
            # Constraint condicional que assegura que o apelido de login rápido 
            # não se repita na mesma clínica (evitando conflitos de login por apelido)
            models.UniqueConstraint(
                fields=['tenant', 'login_alias'],
                condition=models.Q(login_alias__gt=''),
                name='uq_tenant_membership_login_alias'
            ),
        ]
        indexes = [
            models.Index(fields=['professional', 'is_active']),
            models.Index(fields=['tenant', 'role']),
            models.Index(fields=['tenant', 'login_alias']),
        ]

    def __str__(self):
        return f'{self.professional.first_name} @ {self.tenant.name} ({self.get_role_display()})'
