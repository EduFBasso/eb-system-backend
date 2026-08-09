from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Professional, DeviceSession, ProfessionalSettings, Tenant, TenantMembership


@admin.register(Professional)
class ProfessionalAdmin(UserAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "specialty",
        "password_status",
        "is_active",
        "is_staff",
    )
    search_fields = ("first_name", "last_name", "email", "register_number")
    list_filter = ("is_active", "is_staff")
    readonly_fields = ("last_login", "created_at", "password_status")
    ordering = ("email",)

    # Herda o campo de senha com link para redefinição do UserAdmin
    fieldsets = (
        (None, {
            "fields": ("email", "password", "password_status")
        }),
        ("Dados", {
            "fields": (
                "first_name",
                "last_name",
                "display_name",
                "phone",
                "register_number",
                "specialty",
                "can_manage_professionals",
            )
        }),
        ("Endereço", {"fields": ("city", "state")}),
        ("Permissões", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "specialty", "password1", "password2"),
        }),
    )
    filter_horizontal = ("groups", "user_permissions")

    # UserAdmin usa username; nosso model usa email
    USERNAME_FIELD = "email"

    def password_status(self, obj):
        if not obj.pk:
            return "—"
        if obj.has_usable_password():
            return format_html('<span style="color:green">✅ Senha definida</span>')
        return format_html('<span style="color:red">⚠️ Sem senha (somente OTP/TOTP)</span>')

    password_status.short_description = "Status da senha"


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ("professional", "device_id", "is_active", "created_at", "last_seen_at", "terminated_at")
    list_filter = ("is_active", "professional")
    search_fields = ("professional__email", "device_id")
    readonly_fields = ("created_at", "last_seen_at", "terminated_at")


class TenantMembershipInline(admin.TabularInline):
    model = TenantMembership
    extra = 0
    autocomplete_fields = ['professional']


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'ecosystem', 'is_active', 'updated_at']
    list_filter = ['ecosystem', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}
    inlines = [TenantMembershipInline]


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'professional', 'role', 'login_alias', 'is_active']
    list_filter = ['role', 'is_active', 'tenant']
    search_fields = ['tenant__name', 'tenant__slug', 'professional__email', 'login_alias']
    autocomplete_fields = ['tenant', 'professional']



@admin.register(ProfessionalSettings)
class ProfessionalSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "professional",
        "pix_key_type",
        "pix_key_value",
        "work_start_hour",
        "work_start_minute",
        "work_end_hour",
        "work_end_minute",
        "slot_minutes",
        "default_duration_minutes",
        "default_visit_type",
        "updated_at",
    )
    search_fields = ("professional__email", "pix_key_value")
    list_filter = ("pix_key_type",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Profissional", {"fields": ("professional",)}),
        (
            "Agenda padrão",
            {
                "fields": (
                    "work_start_hour",
                    "work_start_minute",
                    "work_end_hour",
                    "work_end_minute",
                    "slot_minutes",
                    "default_duration_minutes",
                    "default_visit_type",
                )
            },
        ),
        (
            "Mensageria",
            {"fields": ("confirm_message_enabled", "confirm_message_template")},
        ),
        (
            "PIX",
            {"fields": ("pix_key_type", "pix_key_value")},
        ),
        ("Datas", {"fields": ("created_at", "updated_at")}),
    )



