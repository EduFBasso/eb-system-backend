from django.contrib import admin
from .models import Supplier, Product, StockMove, Service, ServiceMaterial


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "professional", "email", "phone", "city", "state")
    search_fields = ("name", "email", "phone", "city")
    list_filter = ("state",)


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


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("product", "move_type", "quantity", "unit_cost", "created_at", "professional")
    list_filter = ("move_type",)
    search_fields = ("product__name", "reason", "reference")
    date_hierarchy = "created_at"


class ServiceMaterialInline(admin.TabularInline):
    model = ServiceMaterial
    extra = 1


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "professional", "base_price", "duration_minutes", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)
    inlines = [ServiceMaterialInline]
