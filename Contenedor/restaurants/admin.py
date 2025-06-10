from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Tenant, Restaurant, Table, TableScanLog, 
    Waiter, WaiterNotification,
    KitchenStaff, BarStaff, WaiterStaff
)

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

@admin.register(Waiter)
class WaiterAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 
        'restaurant', 
        'status_badge', 
        'assigned_tables_count',
        'is_available',
        'is_working_hours',
        'last_active'
    ]
    list_filter = [
        'restaurant', 
        'status', 
        'is_available', 
        'notification_email',
        'created_at'
    ]
    search_fields = [
        'user__first_name', 
        'user__last_name', 
        'user__username',
        'employee_id',
        'restaurant__name'
    ]
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('restaurant', 'user', 'employee_id', 'phone')
        }),
        ('Estado Laboral', {
            'fields': ('status', 'is_available', 'shift_start', 'shift_end')
        }),
        ('Configuración de Notificaciones', {
            'fields': ('notification_email', 'notification_push', 'notification_sound'),
            'classes': ('collapse',)
        }),
        ('Estadísticas', {
            'fields': ('total_orders_served', 'average_response_time', 'rating_average'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_active'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at', 'last_active']
    
    def status_badge(self, obj):
        """Mostrar estado con colores"""
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'on_break': 'orange',
            'busy': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'restaurant')


@admin.register(WaiterNotification)
class WaiterNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'waiter',
        'table',
        'notification_type_badge',
        'priority_badge',
        'status_badge',
        'created_at'
    ]
    list_filter = [
        'notification_type',
        'status',
        'priority',
        'waiter__restaurant',
        'created_at'
    ]
    search_fields = [
        'title',
        'waiter__user__first_name',
        'waiter__user__last_name',
        'table__number',
        'order__order_number'
    ]
    readonly_fields = ['created_at', 'read_at', 'responded_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('waiter', 'table', 'order', 'notification_type', 'title', 'message')
        }),
        ('Estado y Prioridad', {
            'fields': ('status', 'priority')
        }),
        ('Metadatos', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'read_at', 'responded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def notification_type_badge(self, obj):
        """Badge para tipo de notificación"""
        colors = {
            'new_order': '#007bff',
            'order_ready': '#28a745',
            'customer_request': '#ffc107',
            'table_call': '#17a2b8',
            'urgent': '#dc3545'
        }
        color = colors.get(obj.notification_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_notification_type_display()
        )
    notification_type_badge.short_description = 'Tipo'
    
    def priority_badge(self, obj):
        """Badge para prioridad"""
        colors = {1: '#28a745', 2: '#ffc107', 3: '#dc3545'}
        labels = {1: 'Normal', 2: 'Alta', 3: 'Urgente'}
        color = colors.get(obj.priority, '#6c757d')
        label = labels.get(obj.priority, 'Normal')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            label
        )
    priority_badge.short_description = 'Prioridad'
    
    def status_badge(self, obj):
        """Badge para estado"""
        colors = {
            'pending': '#ffc107',
            'read': '#17a2b8',
            'responded': '#28a745',
            'dismissed': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('waiter__user', 'table', 'order')


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ['number', 'restaurant', 'display_name', 'assigned_waiter', 'capacity', 'is_active', 'qr_enabled', 'total_scans', 'total_orders']
    list_filter = ['restaurant', 'assigned_waiter', 'is_active', 'qr_enabled', 'capacity', 'created_at']
    search_fields = ['number', 'name', 'restaurant__name', 'assigned_waiter__user__first_name', 'assigned_waiter__user__last_name']
    readonly_fields = ['qr_code_uuid', 'total_scans', 'last_scan', 'total_orders', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('restaurant', 'number', 'name', 'capacity', 'location')
        }),
        ('Asignación de Personal', {
            'fields': ('assigned_waiter',)
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

# ============================================================================
# 👨‍🍳 ADMINISTRACIÓN DE NUEVOS EMPLEADOS
# ============================================================================

class BaseEmployeeAdmin(admin.ModelAdmin):
    """Clase base para administradores de empleados"""
    
    list_filter = [
        'restaurant', 
        'status', 
        'is_available', 
        'notification_email',
        'created_at'
    ]
    search_fields = [
        'user__first_name', 
        'user__last_name', 
        'user__username',
        'employee_id',
        'restaurant__name'
    ]
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at', 'last_active']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('restaurant', 'user', 'employee_id', 'phone')
        }),
        ('Estado Laboral', {
            'fields': ('status', 'is_available', 'shift_start', 'shift_end')
        }),
        ('Configuración de Notificaciones', {
            'fields': ('notification_email', 'notification_push', 'notification_sound'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_active'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Mostrar estado con colores"""
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'on_break': 'orange',
            'busy': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def get_queryset(self, request):
        """Optimizar queries"""
        return super().get_queryset(request).select_related('user', 'restaurant')


@admin.register(KitchenStaff)
class KitchenStaffAdmin(BaseEmployeeAdmin):
    list_display = [
        'full_name', 
        'restaurant', 
        'role_display',
        'status_badge', 
        'total_dishes_prepared',
        'average_prep_time',
        'is_available',
        'last_active'
    ]
    
    # Agregar campos específicos de cocina a fieldsets
    fieldsets = BaseEmployeeAdmin.fieldsets + (
        ('Configuración de Cocina', {
            'fields': ('specialties', 'priority_level', 'can_modify_prep_time'),
            'classes': ('collapse',)
        }),
        ('Estadísticas de Cocina', {
            'fields': ('total_dishes_prepared', 'average_prep_time'),
            'classes': ('collapse',)
        }),
    )
    
    list_filter = BaseEmployeeAdmin.list_filter + ['priority_level', 'can_modify_prep_time']
    
    def role_display(self, obj):
        """Mostrar rol con colores según prioridad"""
        colors = {1: '#6c757d', 2: '#0d6efd', 3: '#dc3545'}  # Junior, Senior, Chef
        color = colors.get(obj.priority_level, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.role_display
        )
    role_display.short_description = 'Rol'


@admin.register(BarStaff)
class BarStaffAdmin(BaseEmployeeAdmin):
    list_display = [
        'full_name', 
        'restaurant', 
        'role_display',
        'status_badge', 
        'total_drinks_prepared',
        'average_prep_time',
        'can_serve_alcohol',
        'is_available',
        'last_active'
    ]
    
    # Agregar campos específicos de bar a fieldsets
    fieldsets = BaseEmployeeAdmin.fieldsets + (
        ('Configuración de Bar', {
            'fields': ('drink_specialties', 'has_bartender_license', 'can_serve_alcohol'),
            'classes': ('collapse',)
        }),
        ('Estadísticas de Bar', {
            'fields': ('total_drinks_prepared', 'average_prep_time'),
            'classes': ('collapse',)
        }),
    )
    
    list_filter = BaseEmployeeAdmin.list_filter + ['has_bartender_license', 'can_serve_alcohol']
    
    def role_display(self, obj):
        """Mostrar rol con indicador de certificación"""
        if obj.has_bartender_license:
            return format_html(
                '<span style="color: #198754; font-weight: bold;">🍸 Barman Certificado</span>'
            )
        return format_html(
            '<span style="color: #0d6efd;">🥤 Preparador de Bebidas</span>'
        )
    role_display.short_description = 'Rol'


@admin.register(WaiterStaff)
class WaiterStaffAdmin(BaseEmployeeAdmin):
    list_display = [
        'full_name', 
        'restaurant', 
        'role_display',
        'status_badge', 
        'total_orders_served',
        'max_tables_assigned',
        'can_take_orders',
        'is_available',
        'last_active'
    ]
    
    # Agregar campos específicos de garzón a fieldsets
    fieldsets = BaseEmployeeAdmin.fieldsets + (
        ('Configuración de Servicio', {
            'fields': ('can_take_orders', 'max_tables_assigned'),
            'classes': ('collapse',)
        }),
        ('Estadísticas de Servicio', {
            'fields': ('total_orders_served', 'average_response_time', 'rating_average'),
            'classes': ('collapse',)
        }),
    )
    
    list_filter = BaseEmployeeAdmin.list_filter + ['can_take_orders']
    
    def role_display(self, obj):
        """Mostrar rol de garzón"""
        return format_html(
            '<span style="color: #fd7e14; font-weight: bold;">🍽️ Garzón de Servicio</span>'
        )
    role_display.short_description = 'Rol'


# Configuraciones adicionales del admin
admin.site.site_header = 'Administración GarzonGoQR'
admin.site.site_title = 'GarzonGoQR Admin'
admin.site.index_title = 'Panel de Administración'
