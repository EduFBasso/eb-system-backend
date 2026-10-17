from django.contrib import admin

from .models import (
    LegalCase,
    LegalCaseParty,
    LegalClient,
    LegalLawyerProfile,
    LegalPerson,
    LegalRepresentation,
)


@admin.register(LegalLawyerProfile)
class LegalLawyerProfileAdmin(admin.ModelAdmin):
    list_display = ("official_name", "oab_number", "oab_state", "tenant", "is_active")
    list_filter = ("tenant", "oab_state", "is_active")
    search_fields = ("official_name", "oab_number", "system_user__email")


@admin.register(LegalClient)
class LegalClientAdmin(admin.ModelAdmin):
    list_display = ("person", "tenant", "status", "created_by", "created_at")
    list_filter = ("tenant", "status")
    search_fields = ("person__name", "person__document", "person__email")


@admin.register(LegalCase)
class LegalCaseAdmin(admin.ModelAdmin):
    list_display = ("title", "case_number", "tenant", "client", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("title", "case_number", "court")


@admin.register(LegalPerson)
class LegalPersonAdmin(admin.ModelAdmin):
    list_display = ("name", "person_type", "document", "tenant")
    list_filter = ("tenant", "person_type")
    search_fields = ("name", "document", "email")


@admin.register(LegalCaseParty)
class LegalCasePartyAdmin(admin.ModelAdmin):
    list_display = ("case", "person", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("case__title", "person__name")


@admin.register(LegalRepresentation)
class LegalRepresentationAdmin(admin.ModelAdmin):
    list_display = ("party", "lawyer", "representation_type", "is_active")
    list_filter = ("representation_type", "is_active")
    search_fields = ("party__person__name", "lawyer__official_name")
