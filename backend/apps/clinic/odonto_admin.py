from django.contrib import admin

from .models import DentalArcade, Tooth, Surface, Procedure


@admin.register(DentalArcade)
class DentalArcadeAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'professional',
        'client',
        'status',
        'external_treatment_id',
        'updated_at',
    )
    list_filter = ('professional', 'status')
    search_fields = ('client__first_name', 'client__last_name', 'external_treatment_id')


@admin.register(Tooth)
class ToothAdmin(admin.ModelAdmin):
    list_display = ('id', 'arcade', 'sequence', 'international_number', 'updated_at')
    list_filter = ('arcade__professional',)
    search_fields = ('arcade__id', 'international_number')


@admin.register(Surface)
class SurfaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'tooth', 'code', 'label', 'updated_at')
    list_filter = ('tooth__arcade__professional', 'code')
    search_fields = ('tooth__international_number',)


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'arcade',
        'name',
        'code',
        'status',
        'external_item_id',
        'is_active',
        'updated_at',
    )
    list_filter = ('arcade__professional', 'status', 'is_active')
    search_fields = ('name', 'code', 'external_item_id', 'arcade__client__first_name')
