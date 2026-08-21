from django.contrib import admin

from .models import DentalProcedureContext, TreatmentPlan, TreatmentPlanItem


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'client', 'status', 'external_treatment_id', 'updated_at')
    list_filter = ('professional', 'status')
    search_fields = ('client__first_name', 'client__last_name', 'external_treatment_id')
    autocomplete_fields = ('professional', 'client')


@admin.register(TreatmentPlanItem)
class TreatmentPlanItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'plan', 'kind', 'status', 'external_item_id', 'is_active', 'updated_at')
    list_filter = ('plan__professional', 'kind', 'status', 'is_active')
    search_fields = ('custom_name', 'service__name', 'product__name', 'external_item_id')
    autocomplete_fields = ('plan', 'service', 'product', 'parent_item')


@admin.register(DentalProcedureContext)
class DentalProcedureContextAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'scope', 'tooth_number', 'tooth_surface', 'arcade_arch')
    list_filter = ('scope', 'arcade_arch')
    search_fields = ('tooth_number', 'item__custom_name')
    autocomplete_fields = ('item',)
