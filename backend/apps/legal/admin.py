from django.contrib import admin

from .models import LegalCase, LegalClient, LegalLawyerProfile


@admin.register(LegalLawyerProfile)
class LegalLawyerProfileAdmin(admin.ModelAdmin):
    list_display = ("official_name", "oab_number", "oab_state", "tenant", "is_active")
    list_filter = ("tenant", "oab_state", "is_active")
    search_fields = ("official_name", "oab_number", "system_user__email")


@admin.register(LegalClient)
class LegalClientAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "status", "created_by", "created_at")
    list_filter = ("tenant", "status")
    search_fields = ("name", "document", "email")


@admin.register(LegalCase)
class LegalCaseAdmin(admin.ModelAdmin):
    list_display = ("title", "case_number", "tenant", "client", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("title", "case_number", "court")
