from django.contrib import admin
from .models import Appointment, Charge, ChargeItem, ClinicalRecord, Encounter


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "professional", "client", "start_at", "end_at", "status")
    list_filter = ("status", "visit_type", "professional")
    search_fields = ("title", "notes", "client__first_name", "client__last_name")
    autocomplete_fields = ("professional", "client")


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "professional", "appointment", "status", "started_at", "ended_at")
    list_filter = ("status", "professional")
    search_fields = ("client__first_name", "client__last_name", "chief_complaint", "notes")
    autocomplete_fields = ("professional", "client", "appointment")


@admin.register(ClinicalRecord)
class ClinicalRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "professional", "record_type", "recorded_at", "is_confidential")
    list_filter = ("record_type", "is_confidential", "professional")
    search_fields = ("title", "content", "client__first_name", "client__last_name")
    autocomplete_fields = ("professional", "client", "encounter")


class ChargeItemInline(admin.TabularInline):
    model = ChargeItem
    extra = 0


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ("id", "charge_type", "status", "client", "professional", "total_amount", "created_at")
    list_filter = ("charge_type", "status", "professional")
    search_fields = ("title", "notes", "recipient_name", "client__first_name", "client__last_name")
    autocomplete_fields = ("professional", "client", "encounter", "appointment")
    inlines = [ChargeItemInline]
