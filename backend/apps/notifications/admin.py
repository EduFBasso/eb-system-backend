from django.contrib import admin

from .models import TelegramProfessionalLink


@admin.register(TelegramProfessionalLink)
class TelegramProfessionalLinkAdmin(admin.ModelAdmin):
    list_display = (
        "professional",
        "tenant",
        "chat_id",
        "telegram_username",
        "is_active",
        "linked_at",
    )
    search_fields = (
        "professional__email",
        "professional__first_name",
        "professional__last_name",
        "chat_id",
        "telegram_username",
    )
    list_filter = ("is_active", "linked_at")
    autocomplete_fields = ("professional", "tenant")
