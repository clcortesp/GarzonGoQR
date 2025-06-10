from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_price',)
    fields = (
        'menu_item', 'quantity', 'selected_variant', 
        'unit_price', 'total_price', 'special_instructions'
    )


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('timestamp', 'changed_by')
    fields = ('previous_status', 'new_status', 'changed_by', 'notes', 'timestamp')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'customer_name', 'restaurant', 'status', 
        'order_type', 'total_amount', 'created_at', 'view_link'
    )
    list_filter = (
        'status', 'order_type', 'payment_method', 'payment_status',
        'restaurant', 'created_at'
    )
    search_fields = (
        'order_number', 'customer_name', 'customer_phone', 
        'customer_email', 'restaurant__name'
    )
    readonly_fields = (
        'id', 'order_number', 'created_at', 'updated_at',
        'confirmed_at', 'ready_at', 'delivered_at'
    )
    
    fieldsets = (
        ('Información del Pedido', {
            'fields': (
                'id', 'order_number', 'restaurant', 'status',
                'order_type', 'estimated_preparation_time'
            )
        }),
        ('Información del Cliente', {
            'fields': (
                'customer_user', 'customer_name', 'customer_phone',
                'customer_email', 'table_number', 'delivery_address'
            )
        }),
        ('Precios', {
            'fields': (
                'subtotal', 'tax_amount', 'delivery_fee',
                'discount_amount', 'total_amount'
            )
        }),
        ('Pago', {
            'fields': ('payment_method', 'payment_status')
        }),
        ('Notas', {
            'fields': ('customer_notes', 'internal_notes')
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at', 'confirmed_at',
                'ready_at', 'delivered_at'
            )
        }),
        ('Calificación', {
            'fields': ('rating', 'review'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    def view_link(self, obj):
        if obj.pk:
            url = reverse('orders:order_detail', kwargs={
                'tenant_slug': obj.restaurant.tenant.slug,
                'order_id': obj.id
            })
            return format_html('<a href="{}" target="_blank">Ver Pedido</a>', url)
        return '-'
    view_link.short_description = 'Ver'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('restaurant__tenant', 'customer_user')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order', 'menu_item', 'quantity', 'selected_variant',
        'total_price', 'status'
    )
    list_filter = ('status', 'order__restaurant', 'menu_item__category')
    search_fields = (
        'order__order_number', 'menu_item__name',
        'order__customer_name'
    )
    readonly_fields = ('total_price',)
    
    fieldsets = (
        ('Información del Item', {
            'fields': (
                'order', 'menu_item', 'quantity', 'selected_variant'
            )
        }),
        ('Precios', {
            'fields': (
                'unit_price', 'variant_price', 'addons_price',
                'modifiers_price', 'total_price'
            )
        }),
        ('Configuración', {
            'fields': ('special_instructions', 'status')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order', 'menu_item', 'selected_variant'
        ).prefetch_related('selected_addons', 'selected_modifiers')


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'order', 'previous_status', 'new_status',
        'changed_by', 'timestamp'
    )
    list_filter = ('new_status', 'previous_status', 'timestamp')
    search_fields = ('order__order_number', 'notes')
    readonly_fields = ('timestamp',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order', 'changed_by') 