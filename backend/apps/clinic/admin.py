from django.contrib import admin

from .models import (
    AnamneseBase,
    AnamneseOdontologia,
    AnamnesePodologia,
    Appointment,
    Charge,
    ChargeItem,
    Client,
    ClinicalRecord,
    DentalProcedureContext,
    Encounter,
    PodologyProcedureContext,
    Product,
    ReminderDelivery,
    Service,
    ServiceMaterial,
    StockMove,
    Supplier,
    TreatmentPlan,
    TreatmentPlanItem,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "city", "state", "tenant")
    search_fields = ("first_name", "last_name", "email", "phone")
    list_filter = ("tenant", "city", "state")
    autocomplete_fields = ("tenant",)


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


@admin.register(AnamneseBase)
class AnamneseBaseAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "professional", "tenant", "updated_at")
    list_filter = ("professional", "tenant")
    search_fields = ("client__first_name", "client__last_name", "clinical_history")
    autocomplete_fields = ("client", "professional")


@admin.register(AnamnesePodologia)
class AnamnesePodologiaAdmin(admin.ModelAdmin):
    list_display = ("id", "anamnese_base", "professional", "updated_at")
    list_filter = ("professional",)
    search_fields = ("anamnese_base__client__first_name", "anamnese_base__client__last_name", "other_procedures")
    autocomplete_fields = ("anamnese_base", "professional")


@admin.register(AnamneseOdontologia)
class AnamneseOdontologiaAdmin(admin.ModelAdmin):
    list_display = ("id", "anamnese_base", "professional", "updated_at")
    list_filter = ("professional",)
    search_fields = (
        "anamnese_base__client__first_name",
        "anamnese_base__client__last_name",
        "chief_dental_complaint",
    )
    autocomplete_fields = ("anamnese_base", "professional")


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "professional", "client", "status", "external_treatment_id", "updated_at")
    list_filter = ("professional", "status")
    search_fields = ("client__first_name", "client__last_name", "external_treatment_id")
    autocomplete_fields = ("professional", "client")


@admin.register(TreatmentPlanItem)
class TreatmentPlanItemAdmin(admin.ModelAdmin):
    list_display = ("id", "plan", "kind", "status", "external_item_id", "is_active", "updated_at")
    list_filter = ("plan__professional", "kind", "status", "is_active")
    search_fields = ("custom_name", "service__name", "product__name", "external_item_id")
    autocomplete_fields = ("plan", "service", "product", "parent_item")


@admin.register(DentalProcedureContext)
class DentalProcedureContextAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "scope", "tooth_number", "tooth_surface", "arcade_arch")
    list_filter = ("scope", "arcade_arch")
    search_fields = ("tooth_number", "item__custom_name")
    autocomplete_fields = ("item",)


@admin.register(PodologyProcedureContext)
class PodologyProcedureContextAdmin(admin.ModelAdmin):
    list_display = ("id", "treatment_plan_item", "scope", "location_number", "tenant")
    list_filter = ("scope", "tenant")
    search_fields = ("treatment_plan_item__custom_name",)
    autocomplete_fields = ("treatment_plan_item", "tenant")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "email", "phone", "city", "state")
    search_fields = ("name", "email", "phone", "city")
    list_filter = ("state",)
    autocomplete_fields = ("tenant",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "tenant",
        "unit",
        "price",
        "track_inventory",
        "quantity_on_hand",
        "is_active",
    )
    list_filter = ("type", "track_inventory", "is_active")
    search_fields = ("name", "scientific_name", "sku")
    autocomplete_fields = ("tenant", "supplier")


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("product", "move_type", "quantity", "unit_cost", "created_at")
    list_filter = ("move_type",)
    search_fields = ("product__name", "reason", "reference")
    date_hierarchy = "created_at"
    autocomplete_fields = ("product",)


class ServiceMaterialInline(admin.TabularInline):
    model = ServiceMaterial
    extra = 1


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "base_price", "duration_minutes", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)
    inlines = [ServiceMaterialInline]
    autocomplete_fields = ("tenant",)


@admin.register(ReminderDelivery)
class ReminderDeliveryAdmin(admin.ModelAdmin):
    list_display = ("appointment", "professional", "channel", "status", "attempted_at", "sent_at")
    search_fields = (
        "professional__email",
        "appointment__title",
        "appointment__client__first_name",
        "appointment__client__last_name",
        "external_message_id",
    )
    list_filter = ("channel", "status", "attempted_at")
    autocomplete_fields = ("appointment", "professional")
