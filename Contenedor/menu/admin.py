from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.utils.safestring import SafeString
from .models import MenuCategory, MenuItem, MenuVariant, MenuAddon, MenuModifier


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'tenant_info', 'items_count', 'is_active_display', 
        'order', 'availability_display', 'created_at'
    ]
    list_filter = ['tenant', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'tenant__name']
    ordering = ['tenant__name', 'order', 'name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('tenant', 'name', 'slug', 'description')
        }),
        ('Configuración', {
            'fields': ('order', 'is_active', 'image')
        }),
        ('Horarios de Disponibilidad', {
            'fields': ('available_from', 'available_until'),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def tenant_info(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            obj.tenant.primary_color,
            obj.tenant.name
        )
    tenant_info.short_description = 'Restaurante'
    
    def items_count(self, obj):
        count = obj.active_items_count
        color = '#28a745' if count > 0 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, count
        )
    items_count.short_description = 'Productos Activos'
    
    def is_active_display(self, obj):
        return obj.is_active
    is_active_display.short_description = 'Estado'
    is_active_display.boolean = True
    
    def availability_display(self, obj):
        if obj.available_from and obj.available_until:
            return f"{obj.available_from} - {obj.available_until}"
        return "Todo el día"
    availability_display.short_description = 'Horario'


class MenuVariantInline(admin.TabularInline):
    model = MenuVariant
    extra = 0
    fields = ['variant_type', 'name', 'price_modifier', 'is_default', 'is_available', 'order']


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category_info', 'tenant_info', 'price_display', 
        'availability_status', 'is_featured_display', 'dietary_tags', 'created_at'
    ]
    list_filter = [
        'tenant', 'category', 'is_available', 'is_featured', 
        'is_vegetarian', 'is_vegan', 'is_gluten_free', 'is_spicy'
    ]
    search_fields = ['name', 'description', 'tenant__name', 'category__name']
    ordering = ['tenant__name', 'category__order', 'order', 'name']
    readonly_fields = ['created_at', 'updated_at', 'discount_info', 'stock_status']
    inlines = [MenuVariantInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('tenant', 'category', 'name', 'slug', 'description', 'short_description')
        }),
        ('Precios', {
            'fields': ('base_price', 'discounted_price', 'discount_info')
        }),
        ('Disponibilidad y Stock', {
            'fields': ('is_available', 'stock_quantity', 'stock_status', 'order')
        }),
        ('Características', {
            'fields': ('is_featured', 'preparation_time', 'calories'),
            'classes': ('collapse',)
        }),
        ('Multimedia', {
            'fields': ('image', 'gallery_images'),
            'classes': ('collapse',)
        }),
        ('Información Dietética', {
            'fields': (
                'is_vegetarian', 'is_vegan', 'is_gluten_free', 
                'is_spicy', 'allergens'
            ),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def tenant_info(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            obj.tenant.primary_color,
            obj.tenant.name
        )
    tenant_info.short_description = 'Restaurante'
    
    def category_info(self, obj):
        return f"{obj.category.name}"
    category_info.short_description = 'Categoría'
    
    def price_display(self, obj):
        if obj.has_discount:
            return format_html(
                '<span style="text-decoration: line-through; color: #6c757d;">${}</span><br>'
                '<span style="color: #dc3545; font-weight: bold;">${} (-{}%)</span>',
                obj.base_price, obj.current_price, obj.discount_percentage
            )
        return format_html('<span style="font-weight: bold;">${}</span>', obj.current_price)
    price_display.short_description = 'Precio'
    
    def availability_status(self, obj):
        if not obj.is_available:
            return format_html('<span style="color: #dc3545;">❌ No disponible</span>')
        if not obj.is_in_stock:
            return format_html('<span style="color: #ffc107;">⚠️ Sin stock</span>')
        return format_html('<span style="color: #28a745;">✅ Disponible</span>')
    availability_status.short_description = 'Estado'
    
    def is_featured_display(self, obj):
        return obj.is_featured
    is_featured_display.short_description = 'Destacado'
    is_featured_display.boolean = True
    
    def dietary_tags(self, obj):
        tags = []
        if obj.is_vegetarian:
            tags.append('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">🥗 VEG</span>')
        if obj.is_vegan:
            tags.append('<span style="background: #20c997; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">🌱 VEGAN</span>')
        if obj.is_gluten_free:
            tags.append('<span style="background: #17a2b8; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">🚫 S/GLUTEN</span>')
        if obj.is_spicy:
            tags.append('<span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">🌶️ PICANTE</span>')
        
        return format_html(' '.join(tags)) if tags else "-"
    dietary_tags.short_description = 'Características'
    
    def discount_info(self, obj):
        if obj.has_discount:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">{}% de descuento</span>',
                obj.discount_percentage
            )
        return "Sin descuento"
    discount_info.short_description = 'Info de Descuento'
    
    def stock_status(self, obj):
        if obj.stock_quantity is None:
            return format_html('<span style="color: #28a745;">Stock ilimitado</span>')
        elif obj.stock_quantity > 10:
            return format_html('<span style="color: #28a745;">En stock ({})</span>', obj.stock_quantity)
        elif obj.stock_quantity > 0:
            return format_html('<span style="color: #ffc107;">Stock bajo ({})</span>', obj.stock_quantity)
        else:
            return format_html('<span style="color: #dc3545;">Sin stock</span>')
    stock_status.short_description = 'Estado del Stock'


@admin.register(MenuVariant)
class MenuVariantAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'menu_item_info', 'variant_type', 'price_modifier_display', 
        'is_default_display', 'is_available_display'
    ]
    list_filter = ['tenant', 'variant_type', 'is_default', 'is_available']
    search_fields = ['name', 'menu_item__name', 'tenant__name']
    ordering = ['tenant__name', 'menu_item__name', 'variant_type', 'order']
    
    def menu_item_info(self, obj):
        return f"{obj.menu_item.name} ({obj.tenant.name})"
    menu_item_info.short_description = 'Producto'
    
    def price_modifier_display(self, obj):
        if obj.price_modifier > 0:
            return format_html('<span style="color: #dc3545;">+${}</span>', obj.price_modifier)
        elif obj.price_modifier < 0:
            return format_html('<span style="color: #28a745;">${}</span>', obj.price_modifier)
        return "Sin cambio"
    price_modifier_display.short_description = 'Modificador'
    
    def is_default_display(self, obj):
        return obj.is_default
    is_default_display.short_description = 'Por Defecto'
    is_default_display.boolean = True
    
    def is_available_display(self, obj):
        return obj.is_available
    is_available_display.short_description = 'Disponible'
    is_available_display.boolean = True


@admin.register(MenuAddon)
class MenuAddonAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'addon_type', 'price_display', 'tenant_info', 
        'compatible_items_count', 'is_available_display'
    ]
    list_filter = ['tenant', 'addon_type', 'is_available']
    search_fields = ['name', 'description', 'tenant__name']
    filter_horizontal = ['menu_items']
    
    def price_display(self, obj):
        return format_html('<span style="font-weight: bold; color: #28a745;">${}</span>', obj.price)
    price_display.short_description = 'Precio'
    
    def tenant_info(self, obj):
        return format_html(
            '<span style="color: {};">{}</span>',
            obj.tenant.primary_color,
            obj.tenant.name
        )
    tenant_info.short_description = 'Restaurante'
    
    def compatible_items_count(self, obj):
        count = obj.menu_items.count()
        return format_html('<span style="font-weight: bold;">{} productos</span>', count)
    compatible_items_count.short_description = 'Compatibilidad'
    
    def is_available_display(self, obj):
        return obj.is_available
    is_available_display.short_description = 'Disponible'
    is_available_display.boolean = True


@admin.register(MenuModifier)
class MenuModifierAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'modifier_type', 'price_modifier_display', 'tenant_info',
        'compatible_items_count', 'is_available_display'
    ]
    list_filter = ['tenant', 'modifier_type', 'is_available']
    search_fields = ['name', 'description', 'tenant__name']
    filter_horizontal = ['menu_items']
    
    def price_modifier_display(self, obj):
        if obj.price_modifier > 0:
            return format_html('<span style="color: #dc3545;">+${}</span>', obj.price_modifier)
        elif obj.price_modifier < 0:
            return format_html('<span style="color: #28a745;">${}</span>', obj.price_modifier)
        return "Gratis"
    price_modifier_display.short_description = 'Costo'
    
    def tenant_info(self, obj):
        return format_html(
            '<span style="color: {};">{}</span>',
            obj.tenant.primary_color,
            obj.tenant.name
        )
    tenant_info.short_description = 'Restaurante'
    
    def compatible_items_count(self, obj):
        count = obj.menu_items.count()
        return format_html('<span style="font-weight: bold;">{} productos</span>', count)
    compatible_items_count.short_description = 'Compatibilidad'
    
    def is_available_display(self, obj):
        return obj.is_available
    is_available_display.short_description = 'Disponible'
    is_available_display.boolean = True
