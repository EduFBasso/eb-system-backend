from django.contrib import admin

from .models import BakeryCustomer, CreditLedgerEntry, Order, OrderItem, Product


@admin.register(BakeryCustomer)
class BakeryCustomerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "nickname",
        "customer_type",
        "status",
        "credit_limit",
        "financial_used",
        "financial_available",
        "created_at",
    )
    list_filter = ("tenant", "status", "customer_type", "created_at")
    search_fields = ("nickname", "company_name", "cpf", "cnpj", "phone", "user__email")
    readonly_fields = (
        "financial_limit",
        "financial_used",
        "financial_available",
        "current_balance",
        "available_credit",
        "created_at",
        "updated_at",
    )
    ordering = ("nickname",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "name",
        "price",
        "is_active",
        "created_at",
    )
    list_filter = ("tenant", "is_active", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = (
        "product",
        "quantity",
        "unit_price",
        "subtotal",
        "tenant",
        "created_at",
    )
    readonly_fields = ("unit_price", "subtotal", "tenant", "created_at")
    autocomplete_fields = ("product",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "customer",
        "status",
        "payment_method",
        "total_value",
        "delivery_date",
        "created_at",
    )
    list_filter = (
        "tenant",
        "status",
        "payment_method",
        "created_at",
    )
    search_fields = (
        "id",
        "customer__nickname",
        "customer__company_name",
        "shipping_city",
        "shipping_neighborhood",
    )
    readonly_fields = ("total_value", "created_at", "updated_at")
    ordering = ("-created_at",)
    inlines = (OrderItemInline,)


@admin.register(CreditLedgerEntry)
class CreditLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "customer",
        "entry_type",
        "amount",
        "order",
        "reference_key",
        "created_at",
    )
    list_filter = ("tenant", "entry_type", "created_at")
    search_fields = (
        "customer__nickname",
        "description",
        "reference_key",
        "order__id",
    )
    readonly_fields = (
        "tenant",
        "customer",
        "entry_type",
        "amount",
        "description",
        "order",
        "reference_key",
        "created_at",
    )
    ordering = ("-created_at", "-id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
