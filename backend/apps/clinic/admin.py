from django.contrib import admin

from .models import (
    AnamnesisField,
    AnamnesisResponse,
    AnamneseBase,
    AnamnesePodologia,
    Appointment,
    Charge,
    ChargeItem,
    Client,
    ClinicalRecord,
    DentalArcade,
    Encounter,
    FinalizeAudit,
    Procedure,
    ProcedureNameSuggestion,
    Product,
    ProductCatalogItem,
    ReminderDelivery,
    Service,
    ServiceMaterial,
    StockMove,
    Supplier,
    Surface,
    TelegramProfessionalLink,
    Tooth,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "city", "state", "professional")
    search_fields = ("first_name", "last_name", "email", "phone")
    list_filter = ("professional", "city", "state")
    autocomplete_fields = ("professional",)


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


@admin.register(FinalizeAudit)
class FinalizeAuditAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "professional", "client", "server_now", "created_at")
    list_filter = ("professional",)
    search_fields = ("appointment__title", "client__first_name", "client__last_name", "reason")
    autocomplete_fields = ("appointment", "professional", "client")


@admin.register(AnamneseBase)
class AnamneseBaseAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "professional", "tenant", "updated_at")
    list_filter = ("professional", "tenant")
    search_fields = ("client__first_name", "client__last_name", "clinical_history")
    autocomplete_fields = ("client", "professional")


@admin.register(AnamnesePodologia)
class AnamnesePodologiaAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "professional", "tenant", "updated_at")
    list_filter = ("professional", "tenant")
    search_fields = ("client__first_name", "client__last_name", "other_procedures")
    autocomplete_fields = ("client", "professional")


@admin.register(AnamnesisField)
class AnamnesisFieldAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "code",
        "sector",
        "field_type",
        "selection_mode",
        "depends_on",
        "order",
        "is_active",
        "professional",
    )
    list_filter = ("professional", "sector", "field_type", "selection_mode", "is_active")
    ordering = ("professional", "sector_order", "order")
    search_fields = ("label", "code", "sector")
    autocomplete_fields = ("professional", "depends_on")


@admin.register(AnamnesisResponse)
class AnamnesisResponseAdmin(admin.ModelAdmin):
    list_display = ("client", "field_label_snap", "value", "updated_at")
    list_filter = ("field__professional", "field__sector")
    search_fields = ("client__first_name", "client__last_name", "field_label_snap")
    autocomplete_fields = ("client", "field")


@admin.register(DentalArcade)
class DentalArcadeAdmin(admin.ModelAdmin):
    list_display = ("id", "professional", "client", "status", "external_treatment_id", "updated_at")
    list_filter = ("professional", "status")
    search_fields = ("client__first_name", "client__last_name", "external_treatment_id")
    autocomplete_fields = ("professional", "client")


@admin.register(Tooth)
class ToothAdmin(admin.ModelAdmin):
    list_display = ("id", "arcade", "sequence", "international_number", "updated_at")
    list_filter = ("arcade__professional",)
    search_fields = ("arcade__id", "international_number")
    autocomplete_fields = ("arcade",)


@admin.register(Surface)
class SurfaceAdmin(admin.ModelAdmin):
    list_display = ("id", "tooth", "code", "label", "updated_at")
    list_filter = ("tooth__arcade__professional", "code")
    search_fields = ("tooth__international_number",)
    autocomplete_fields = ("tooth",)


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = ("id", "arcade", "name", "code", "status", "external_item_id", "is_active", "updated_at")
    list_filter = ("arcade__professional", "status", "is_active")
    search_fields = ("name", "code", "external_item_id", "arcade__client__first_name")
    autocomplete_fields = ("arcade", "tooth", "surface", "parent_procedure")


@admin.register(ProcedureNameSuggestion)
class ProcedureNameSuggestionAdmin(admin.ModelAdmin):
    list_display = ("id", "professional", "name", "updated_at")
    search_fields = ("name", "professional__email")
    list_filter = ("professional",)
    autocomplete_fields = ("professional",)


@admin.register(ProductCatalogItem)
class ProductCatalogItemAdmin(admin.ModelAdmin):
    list_display = ("id", "professional", "name", "last_value", "updated_at")
    search_fields = ("name", "professional__email")
    list_filter = ("professional",)
    autocomplete_fields = ("professional",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "professional", "email", "phone", "city", "state")
    search_fields = ("name", "email", "phone", "city")
    list_filter = ("state",)
    autocomplete_fields = ("professional",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "professional",
        "unit",
        "price",
        "track_inventory",
        "quantity_on_hand",
        "is_active",
    )
    list_filter = ("type", "track_inventory", "is_active")
    search_fields = ("name", "scientific_name", "sku")
    autocomplete_fields = ("professional", "supplier")


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("product", "move_type", "quantity", "unit_cost", "created_at", "professional")
    list_filter = ("move_type",)
    search_fields = ("product__name", "reason", "reference")
    date_hierarchy = "created_at"
    autocomplete_fields = ("professional", "product")


class ServiceMaterialInline(admin.TabularInline):
    model = ServiceMaterial
    extra = 1


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "professional", "base_price", "duration_minutes", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)
    inlines = [ServiceMaterialInline]
    autocomplete_fields = ("professional",)


@admin.register(TelegramProfessionalLink)
class TelegramProfessionalLinkAdmin(admin.ModelAdmin):
    list_display = ("professional", "chat_id", "telegram_username", "is_active", "linked_at")
    search_fields = (
        "professional__email",
        "professional__first_name",
        "professional__last_name",
        "chat_id",
        "telegram_username",
    )
    list_filter = ("is_active", "linked_at")
    autocomplete_fields = ("professional",)


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
