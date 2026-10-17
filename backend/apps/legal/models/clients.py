from django.conf import settings
from django.db import models


class LegalClient(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        INACTIVE = "inactive", "Inativo"
        ARCHIVED = "archived", "Arquivado"

    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.CASCADE,
        related_name="legal_clients",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_legal_clients",
    )
    name = models.CharField(max_length=180)
    document = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "status")),
            models.Index(fields=("tenant", "name")),
        ]

    def __str__(self):
        return self.name
