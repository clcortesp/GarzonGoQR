from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from .models import Tenant, Restaurant


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware para detectar el tenant basado en la URL path
    Ejemplo: tuapp.com/restaurante-mario/menu/ -> tenant_slug = 'restaurante-mario'
    """
    
    def process_request(self, request):
        # URLs que no requieren tenant (admin, api root, landing page)
        excluded_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]
        
        # URLs que requieren tenant pero NO deben reescribirse
        api_paths = [
            '/api/',
        ]
        

        
        # Verificar si la URL está excluida
        if any(request.path.startswith(path) for path in excluded_paths):
            print(f"⭕ Path excluido: {request.path}")
            return None
        
        # Extraer el tenant_slug del path
        path_parts = request.path.strip('/').split('/')
        print(f"🔍 Path parts: {path_parts}")
        
        # Si es la raíz del dominio (tuapp.com/)
        if not path_parts or path_parts[0] == '':
            print(f"⭕ Raíz del dominio, sin tenant")
            return None
        
        tenant_slug = path_parts[0]
        print(f"🎯 Tenant slug detectado: '{tenant_slug}'")
        
        try:
            # Buscar el tenant por slug
            tenant = Tenant.objects.select_related('restaurant').get(
                slug=tenant_slug,
                status__in=['ACTIVE', 'TRIAL']
            )
            
            # Inyectar tenant en el request
            request.tenant = tenant
            print(f"✅ Tenant encontrado: {tenant.name}")
            
            # Verificar si el tenant tiene restaurant asociado
            try:
                request.restaurant = tenant.restaurant
                print(f"✅ Restaurant encontrado: {request.restaurant.name}")
            except Restaurant.DoesNotExist:
                # Tenant existe pero no tiene restaurant asociado
                print(f"❌ Tenant sin restaurant: {tenant_slug}")
                raise Http404(f"Restaurante '{tenant_slug}' no está completamente configurado")
            
            # Verificar si es una URL de API - NO reescribir
            remaining_path_parts = path_parts[1:]
            if remaining_path_parts and any(remaining_path_parts[0].startswith(api.strip('/')) for api in api_paths):
                print(f"🔗 API URL detectada, NO reescribiendo: {request.path}")
                return None
            
            # NO reescribir URLs - dejar que Django maneje el routing naturalmente
            # Solo inyectar tenant en el request para que las vistas lo puedan usar
            print(f"✅ Tenant configurado exitosamente - NO reescribiendo URLs")
            print(f"🎯 Path original mantenido: {request.path_info}")
            
        except Tenant.DoesNotExist:
            # Tenant no existe o está inactivo
            raise Http404(f"Restaurante '{tenant_slug}' no encontrado o no disponible")
        
        return None


class TenantContextMiddleware(MiddlewareMixin):
    """
    Middleware para inyectar contexto del tenant en templates
    """
    
    def process_template_response(self, request, response):
        if hasattr(request, 'tenant') and hasattr(response, 'context_data'):
            if response.context_data is None:
                response.context_data = {}
            
            response.context_data.update({
                'tenant': request.tenant,
                'restaurant': getattr(request, 'restaurant', None),
            })
        
        return response


# Utility functions para usar en views
def get_current_tenant(request=None):
    """
    Obtener el tenant actual del request
    """
    if request and hasattr(request, 'tenant'):
        return request.tenant
    return None


def get_current_restaurant(request=None):
    """
    Obtener el restaurant actual del request
    """
    if request and hasattr(request, 'restaurant'):
        return request.restaurant
    return None 