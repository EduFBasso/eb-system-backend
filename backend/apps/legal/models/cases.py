from django.conf import settings
from django.db import models


class LegalCase(models.Model):
    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.CASCADE,
        related_name="legal_cases",
    )
    client = models.ForeignKey(
        "legal.LegalClient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cases",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_legal_cases",
    )
    title = models.CharField(max_length=220)
    case_number = models.CharField(max_length=40, blank=True)
    court = models.CharField(max_length=180, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "is_active")),
            models.Index(fields=("tenant", "case_number")),
        ]

    def __str__(self):
        return self.title
