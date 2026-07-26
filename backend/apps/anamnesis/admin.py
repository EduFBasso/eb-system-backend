from django.contrib import admin
from .models import AnamnesisField, AnamnesisResponse


class AnamnesisFieldAdmin(admin.ModelAdmin):
    list_display = (
        'label',
        'code',
        'sector',
        'field_type',
        'selection_mode',
        'depends_on',
        'order',
        'is_active',
        'professional',
    )
    list_filter = ('professional', 'sector', 'field_type', 'selection_mode', 'is_active')
    ordering = ('professional', 'sector_order', 'order')
    search_fields = ('label', 'code', 'sector')


class AnamnesisResponseAdmin(admin.ModelAdmin):
    list_display = ('client', 'field_label_snap', 'value', 'updated_at')
    list_filter = ('field__professional', 'field__sector')
    search_fields = ('client__first_name', 'client__last_name', 'field_label_snap')


admin.site.register(AnamnesisField, AnamnesisFieldAdmin)
admin.site.register(AnamnesisResponse, AnamnesisResponseAdmin)
