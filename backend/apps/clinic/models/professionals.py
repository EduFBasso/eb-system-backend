from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class ClinicProfessionalProfile(models.Model):
    """Dados profissionais do Clinic, separados da identidade global."""

    system_user = models.ForeignKey(
        "authentication.SystemUser",
        on_delete=models.CASCADE,
        related_name="clinic_profiles",
    )
    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.CASCADE,
        related_name="clinic_professional_profiles",
    )
    register_number = models.CharField(max_length=30, blank=True, null=True)
    specialty = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("system_user", "tenant"),
                name="clinic_profile_unique_user_tenant",
            ),
            models.UniqueConstraint(
                fields=("tenant", "register_number"),
                condition=~models.Q(register_number__isnull=True)
                & ~models.Q(register_number=""),
                name="clinic_profile_unique_register_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "specialty")),
            models.Index(fields=("system_user", "is_active")),
        ]

    def __str__(self):
        return f"{self.system_user} @ {self.tenant}"


class ClinicProfessionalSettings(models.Model):
    """Agenda, lembretes e preferências odontológicas do Clinic."""

    class DefaultVisitType(models.TextChoices):
        CONSULTA = "consulta", "Consulta"
        RETORNO = "retorno", "Retorno"
        OUTRO = "outro", "Outro compromisso"

    professional = models.OneToOneField(
        ClinicProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    work_start_hour = models.PositiveSmallIntegerField(default=6)
    work_start_minute = models.PositiveSmallIntegerField(default=0)
    work_end_hour = models.PositiveSmallIntegerField(default=21)
    work_end_minute = models.PositiveSmallIntegerField(default=0)
    slot_minutes = models.PositiveSmallIntegerField(default=10)
    default_duration_minutes = models.PositiveSmallIntegerField(default=60)
    default_visit_type = models.CharField(
        max_length=20,
        choices=DefaultVisitType.choices,
        default=DefaultVisitType.CONSULTA,
    )
    confirm_message_enabled = models.BooleanField(default=False)
    confirm_message_template = models.TextField(blank=True)
    reminder_enabled = models.BooleanField(default=False)
    reminder_minutes_before = models.PositiveSmallIntegerField(default=90)
    lock_odonto_plan_after_print = models.BooleanField(default=True)
    odonto_quote_validity_days = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Configurações Clinic de {self.professional.system_user.email}"
