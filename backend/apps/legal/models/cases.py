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


class LegalCaseParty(models.Model):
    class Role(models.TextChoices):
        PLAINTIFF = "plaintiff", "Autor"
        DEFENDANT = "defendant", "Réu"
        WITNESS = "witness", "Testemunha"
        THIRD_PARTY = "third_party", "Terceiro"
        OTHER = "other", "Outro"

    case = models.ForeignKey(
        LegalCase,
        on_delete=models.CASCADE,
        related_name="parties",
    )
    person = models.ForeignKey(
        "legal.LegalPerson",
        on_delete=models.PROTECT,
        related_name="case_parties",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("case", "person", "role"),
                name="legal_case_party_unique_role",
            ),
        ]
        indexes = [
            models.Index(fields=("case", "role")),
            models.Index(fields=("person", "is_active")),
        ]


class LegalRepresentation(models.Model):
    class RepresentationType(models.TextChoices):
        PRIMARY = "primary", "Principal"
        CO_COUNSEL = "co_counsel", "Co- representação"
        ASSISTANT = "assistant", "Assistência"

    party = models.ForeignKey(
        LegalCaseParty,
        on_delete=models.CASCADE,
        related_name="representations",
    )
    lawyer = models.ForeignKey(
        "legal.LegalLawyerProfile",
        on_delete=models.PROTECT,
        related_name="case_representations",
    )
    representation_type = models.CharField(
        max_length=20,
        choices=RepresentationType.choices,
        default=RepresentationType.PRIMARY,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("party", "lawyer", "representation_type"),
                name="legal_representation_unique_lawyer_type",
            ),
        ]
