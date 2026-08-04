from django.conf import settings
from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    capabilities = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def has_capability(self, capability_name: str) -> bool:
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
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tenant_memberships',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant membership'
        verbose_name_plural = 'Tenant memberships'
        unique_together = [('tenant', 'professional')]
        indexes = [
            models.Index(fields=['professional', 'is_active']),
            models.Index(fields=['tenant', 'role']),
        ]

    def __str__(self):
        return f'{self.professional} @ {self.tenant} ({self.role})'
