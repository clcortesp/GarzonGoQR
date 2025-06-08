from django.contrib import admin
from django.utils.html import format_html
from .models import Tenant, Restaurant, Table, TableScanLog

# Register your models here.

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'slug', 
        'status_badge', 
        'subscription_plan', 
        'has_logo',
        'created_at',
        'trial_ends_at'
    ]
    list_filter = [
        'status', 
        'subscription_plan', 
        'created_at',
        'trial_ends_at'
    ]
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id', 'created_at']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'slug', 'status', 'subscription_plan')
        }),
        ('Branding', {
            'fields': ('primary_color', 'logo'),
            'classes': ('collapse',)
        }),
        ('Fechas importantes', {
            'fields': ('created_at', 'trial_ends_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Mostrar el status con colores"""
        colors = {
            'ACTIVE': 'green',
            'TRIAL': 'orange', 
            'SUSPENDED': 'red',
            'EXPIRED': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def has_logo(self, obj):
        """Mostrar si tiene logo"""
        return bool(obj.logo)
    has_logo.short_description = 'Logo'
    has_logo.boolean = True

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'tenant_name',
        'tenant_slug', 
        'owner', 
        'status_badge',
        'has_schedule',
        'created_at'
    ]
    list_filter = [
        'is_active', 
        'created_at',
        'tenant__status',
        'tenant__subscription_plan'
    ]
    search_fields = [
        'name', 
        'tenant__name', 
        'tenant__slug',
        'owner__username',
        'owner__email'
    ]
    raw_id_fields = ['owner']  # Para mejor performance con muchos usuarios
    
    fieldsets = (
        ('Información básica', {
            'fields': ('tenant', 'name', 'owner', 'is_active')
        }),
        ('Información de contacto', {
            'fields': ('address', 'phone', 'email')
        }),
        ('Horarios de atención', {
            'fields': ('opening_time', 'closing_time'),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def tenant_name(self, obj):
        """Mostrar nombre del tenant"""
        return obj.tenant.name
    tenant_name.short_description = 'Tenant'
    
    def tenant_slug(self, obj):
        """Mostrar slug del tenant con enlace"""
        return format_html(
            '<a href="/admin/restaurants/tenant/{}/change/" style="color: #0066cc;">{}</a>',
            obj.tenant.id,
            obj.tenant.slug
        )
    tenant_slug.short_description = 'URL Slug'
    
    def status_badge(self, obj):
        """Mostrar estado del restaurante"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">● Activo</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">● Inactivo</span>'
            )
    status_badge.short_description = 'Estado'
    
    def has_schedule(self, obj):
        """Mostrar si tiene horarios configurados"""
        return bool(obj.opening_time and obj.closing_time)
    has_schedule.short_description = 'Horarios'
    has_schedule.boolean = True
    
    def get_queryset(self, request):
        """Optimizar queries para evitar N+1"""
        return super().get_queryset(request).select_related('tenant', 'owner')

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ['number', 'restaurant', 'display_name', 'capacity', 'is_active', 'qr_enabled', 'total_scans', 'total_orders']
    list_filter = ['restaurant', 'is_active', 'qr_enabled', 'capacity', 'created_at']
    search_fields = ['number', 'name', 'restaurant__name']
    readonly_fields = ['qr_code_uuid', 'total_scans', 'last_scan', 'total_orders', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('restaurant', 'number', 'name', 'capacity', 'location')
        }),
        ('Estado', {
            'fields': ('is_active', 'qr_enabled')
        }),
        ('QR Code', {
            'fields': ('qr_code_uuid',),
            'classes': ('collapse',)
        }),
        ('Estadísticas', {
            'fields': ('total_scans', 'last_scan', 'total_orders'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TableScanLog)
class TableScanLogAdmin(admin.ModelAdmin):
    list_display = ['table', 'scanned_at', 'ip_address', 'resulted_in_order', 'order']
    list_filter = ['resulted_in_order', 'scanned_at', 'table__restaurant']
    search_fields = ['table__number', 'table__restaurant__name', 'ip_address']
    readonly_fields = ['scanned_at']
    date_hierarchy = 'scanned_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('table', 'table__restaurant', 'order')

# Configuraciones adicionales del admin
admin.site.site_header = 'Administración GarzonGoQR'
admin.site.site_title = 'GarzonGoQR Admin'
admin.site.index_title = 'Panel de Administración'
