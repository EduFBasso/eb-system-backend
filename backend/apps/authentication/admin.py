from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserCreationForm
from django.utils.html import format_html
from .models import Professional, DeviceSession, ProfessionalSettings, Tenant, TenantMembership


def _normalize_secret_token(value: str) -> str:
    return ''.join(ch for ch in (value or '').lower() if ch.isalnum())


def _password_uses_identity(raw_password: str, professional: Professional, login_alias: str = '') -> bool:
    if not raw_password:
        return False

    normalized_password = _normalize_secret_token(raw_password)
    if not normalized_password:
        return False

    local_part = (professional.email or '').split('@')[0]
    full_name = f"{professional.first_name} {professional.last_name}".strip()
    candidates = [
        professional.first_name,
        professional.last_name,
        full_name,
        professional.email,
        local_part,
        login_alias,
    ]
    normalized_candidates = {_normalize_secret_token(item) for item in candidates if item}
    return normalized_password in normalized_candidates


def _has_duplicate_bakery_owner_name(first_name: str, last_name: str, exclude_professional_id: int | None = None) -> bool:
    queryset = TenantMembership.objects.filter(
        tenant__ecosystem=Tenant.Ecosystem.BAKERY,
        role=TenantMembership.Role.OWNER,
        professional__first_name__iexact=(first_name or '').strip(),
        professional__last_name__iexact=(last_name or '').strip(),
    )
    if exclude_professional_id is not None:
        queryset = queryset.exclude(professional_id=exclude_professional_id)
    return queryset.exists()


def _is_password_reused(raw_password: str, current_user: Professional | None = None) -> bool:
    if not raw_password:
        return False
    queryset = Professional.objects.all()
    if current_user and current_user.pk:
        queryset = queryset.exclude(pk=current_user.pk)
    for professional in queryset.iterator():
        if professional.has_usable_password() and professional.check_password(raw_password):
            return True
    return False


class ProfessionalCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Professional
        fields = ("email", "first_name", "last_name", "specialty")

    def clean(self):
        cleaned_data = super().clean()
        password2 = cleaned_data.get("password2")
        if _is_password_reused(password2):
            raise forms.ValidationError("Esta senha já está em uso por outro profissional.")
        professional = Professional(
            email=(self.cleaned_data.get('email') or '').strip().lower(),
            first_name=(self.cleaned_data.get('first_name') or '').strip(),
            last_name=(self.cleaned_data.get('last_name') or '').strip(),
        )
        if _password_uses_identity(password2, professional):
            raise forms.ValidationError("A senha não pode ser igual ao nome, sobrenome ou e-mail.")
        return cleaned_data


class ProfessionalAdminPasswordChangeForm(AdminPasswordChangeForm):
    def clean(self):
        cleaned_data = super().clean()
        password2 = cleaned_data.get("password2")
        if _is_password_reused(password2, current_user=self.user):
            raise forms.ValidationError("Esta senha já está em uso por outro profissional.")
        if _password_uses_identity(password2, self.user):
            raise forms.ValidationError("A senha não pode ser igual ao nome, sobrenome ou e-mail.")
        return cleaned_data


class TenantMembershipAdminForm(forms.ModelForm):
    class Meta:
        model = TenantMembership
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        tenant = cleaned.get('tenant')
        role = cleaned.get('role')
        professional = cleaned.get('professional')

        if (
            tenant
            and professional
            and tenant.ecosystem == Tenant.Ecosystem.BAKERY
            and role == TenantMembership.Role.OWNER
            and _has_duplicate_bakery_owner_name(
                professional.first_name,
                professional.last_name,
                exclude_professional_id=professional.id,
            )
        ):
            raise forms.ValidationError(
                "Já existe outro owner Bakery com o mesmo nome e sobrenome. Use um nome administrativo diferente."
            )

        return cleaned


@admin.register(Professional)
class ProfessionalAdmin(UserAdmin):
    add_form = ProfessionalCreationForm
    change_password_form = ProfessionalAdminPasswordChangeForm

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
        ("Endereço e dados comerciais", {"fields": (
            "address", "number", "neighborhood", "zip_code", "city", "state", "cnpj",
        )}),
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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.exclude(is_superuser=True).exclude(email__iendswith='@local.invalid')


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
    form = TenantMembershipAdminForm
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



