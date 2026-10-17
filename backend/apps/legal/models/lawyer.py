from django.db import models


class LegalLawyerProfile(models.Model):
    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.CASCADE,
        related_name="legal_lawyer_profiles",
    )
    system_user = models.ForeignKey(
        "authentication.SystemUser",
        on_delete=models.CASCADE,
        related_name="legal_lawyer_profiles",
    )
    oab_number = models.CharField(max_length=20)
    oab_state = models.CharField(max_length=2)
    official_name = models.CharField(max_length=180)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "oab_number", "oab_state"),
                name="legal_lawyer_unique_oab_per_tenant",
            ),
            models.UniqueConstraint(
                fields=("tenant", "system_user"),
                name="legal_lawyer_unique_user_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "official_name")),
            models.Index(fields=("tenant", "is_active")),
        ]

    def __str__(self):
        return f"{self.official_name} - OAB {self.oab_number}/{self.oab_state}"
