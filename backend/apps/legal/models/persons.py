from django.db import models


class LegalPerson(models.Model):
    class PersonType(models.TextChoices):
        INDIVIDUAL = "individual", "Pessoa física"
        COMPANY = "company", "Pessoa jurídica"

    tenant = models.ForeignKey(
        "authentication.Tenant",
        on_delete=models.CASCADE,
        related_name="legal_people",
    )
    person_type = models.CharField(max_length=20, choices=PersonType.choices)
    name = models.CharField(max_length=180)
    document = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=240, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "name")),
            models.Index(fields=("tenant", "document")),
        ]

    def __str__(self):
        return self.name
