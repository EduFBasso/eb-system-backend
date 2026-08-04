from django.contrib import admin

from .models import ReminderDelivery, TelegramProfessionalLink


@admin.register(TelegramProfessionalLink)
class TelegramProfessionalLinkAdmin(admin.ModelAdmin):
    list_display = (
        "professional",
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


@admin.register(ReminderDelivery)
class ReminderDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "appointment",
        "professional",
        "channel",
        "status",
        "attempted_at",
        "sent_at",
    )
    search_fields = (
        "professional__email",
        "appointment__title",
        "appointment__client__first_name",
        "appointment__client__last_name",
        "external_message_id",
    )
    list_filter = ("channel", "status", "attempted_at")