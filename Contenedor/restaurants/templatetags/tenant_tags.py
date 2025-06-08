from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def tenant_url(context, url_name, *args, **kwargs):
    """
    Generar URL con tenant slug automáticamente
    Uso: {% tenant_url 'restaurants:menu' %}
    Genera: /restaurante-mario/menu/
    """
    request = context.get('request')
    
    if request and hasattr(request, 'tenant'):
        # Generar URL normal primero
        url = reverse(url_name, args=args, kwargs=kwargs)
        # Agregar tenant slug al inicio
        return f"/{request.tenant.slug}{url}"
    
    # Fallback si no hay tenant
    return reverse(url_name, args=args, kwargs=kwargs)


@register.simple_tag(takes_context=True)
def tenant_color(context, color_type='primary'):
    """
    Obtener color del tenant
    Uso: {% tenant_color 'primary' %}
    """
    request = context.get('request')
    
    if request and hasattr(request, 'tenant'):
        if color_type == 'primary':
            return request.tenant.primary_color
    
    # Colores por defecto
    defaults = {
        'primary': '#007bff',
        'secondary': '#6c757d',
    }
    return defaults.get(color_type, '#007bff')


@register.simple_tag(takes_context=True)
def tenant_logo(context):
    """
    Obtener URL del logo del tenant
    Uso: {% tenant_logo %}
    """
    request = context.get('request')
    
    if request and hasattr(request, 'tenant') and request.tenant.logo:
        return request.tenant.logo.url
    
    # Logo por defecto
    return '/static/images/default-logo.png'


@register.inclusion_tag('restaurants/partials/tenant_branding.html', takes_context=True)
def tenant_branding(context):
    """
    Incluir CSS de branding del tenant
    Uso: {% tenant_branding %}
    """
    request = context.get('request')
    
    return {
        'tenant': getattr(request, 'tenant', None),
        'restaurant': getattr(request, 'restaurant', None),
    }


@register.filter
def tenant_status_badge(status):
    """
    Filtro para mostrar badge del status
    Uso: {{ tenant.status|tenant_status_badge }}
    """
    badges = {
        'ACTIVE': '<span class="badge bg-success">Activo</span>',
        'TRIAL': '<span class="badge bg-warning">Prueba</span>',
        'SUSPENDED': '<span class="badge bg-danger">Suspendido</span>',
        'EXPIRED': '<span class="badge bg-secondary">Expirado</span>',
    }
    
    return mark_safe(badges.get(status, '<span class="badge bg-secondary">Desconocido</span>'))


@register.simple_tag(takes_context=True)
def qr_scan_url(context, qr_token):
    """
    Generar URL completa para QR scan
    Uso: {% qr_scan_url qr_token %}
    """
    request = context.get('request')
    
    if request and hasattr(request, 'tenant'):
        return f"/{request.tenant.slug}/scan/{qr_token}/"
    
    return f"/scan/{qr_token}/"


@register.simple_tag(takes_context=True)
def tenant_meta_tags(context):
    """
    Generar meta tags personalizados por tenant
    Uso: {% tenant_meta_tags %}
    """
    request = context.get('request')
    
    if request and hasattr(request, 'tenant'):
        tenant = request.tenant
        restaurant = request.restaurant
        
        meta_tags = f'''
        <meta name="description" content="Menú digital de {restaurant.name}. Haz tu pedido fácilmente desde tu mesa.">
        <meta name="keywords" content="{restaurant.name}, menú digital, restaurante, pedidos online">
        <meta property="og:title" content="{restaurant.name} - Menú Digital">
        <meta property="og:description" content="Menú digital de {restaurant.name}">
        <meta property="og:type" content="website">
        <meta name="theme-color" content="{tenant.primary_color}">
        '''
        
        return mark_safe(meta_tags)
    
    return mark_safe('<meta name="description" content="Plataforma de menús digitales">')


@register.simple_tag(takes_context=True)
def tenant_css_vars(context):
    """
    Generar variables CSS personalizadas
    Uso: {% tenant_css_vars %}
    """
    request = context.get('request')
    
    if request and hasattr(request, 'tenant'):
        tenant = request.tenant
        
        css_vars = f'''
        <style>
        :root {{
            --tenant-primary-color: {tenant.primary_color};
            --tenant-primary-rgb: {hex_to_rgb(tenant.primary_color)};
        }}
        </style>
        '''
        
        return mark_safe(css_vars)
    
    return mark_safe('')


def hex_to_rgb(hex_color):
    """Convertir color hex a RGB"""
    hex_color = hex_color.lstrip('#')
    return ', '.join(str(int(hex_color[i:i+2], 16)) for i in (0, 2, 4)) 