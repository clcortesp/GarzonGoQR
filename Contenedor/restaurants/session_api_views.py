"""
Vistas API para el manejo de sesiones de mesa
"""
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .table_session_manager import TableSessionManager
from .models import Tenant
import json


class TableSessionAPIView(View):
    """Vista base para APIs de sesión de mesa"""
    
    def dispatch(self, request, *args, **kwargs):
        # Verificar tenant
        tenant_slug = kwargs.get('tenant_slug')
        self.tenant = get_object_or_404(Tenant, slug=tenant_slug)
        return super().dispatch(request, *args, **kwargs)


@method_decorator(require_POST, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class ExtendSessionAPI(TableSessionAPIView):
    """API para extender sesión de mesa"""
    
    def post(self, request, tenant_slug):
        try:
            # Verificar que hay una sesión activa
            session_data = TableSessionManager.get_active_session(request)
            if not session_data:
                return JsonResponse({
                    'success': False,
                    'error': 'No hay sesión activa para extender'
                })
            
            # Extender sesión (30 minutos más por defecto)
            extended = TableSessionManager.extend_session(request, minutes=30)
            
            if extended:
                # Obtener nueva información de sesión
                session_info = TableSessionManager.get_session_info(request)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Sesión extendida por 30 minutos más',
                    'new_expires_at': session_info['expires_at'].isoformat(),
                    'time_remaining_minutes': session_info['time_remaining_minutes']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'No se pudo extender la sesión'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error interno: {str(e)}'
            })


@method_decorator(require_POST, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EndSessionAPI(TableSessionAPIView):
    """API para finalizar sesión de mesa"""
    
    def post(self, request, tenant_slug):
        try:
            # Invalidar sesión actual
            TableSessionManager.invalidate_session(request)
            
            return JsonResponse({
                'success': True,
                'message': 'Sesión finalizada exitosamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error interno: {str(e)}'
            })


class SessionStatusAPI(TableSessionAPIView):
    """API para obtener estado de la sesión"""
    
    def get(self, request, tenant_slug):
        try:
            session_info = TableSessionManager.get_session_info(request)
            
            if session_info:
                return JsonResponse({
                    'success': True,
                    'has_active_session': True,
                    'session_info': {
                        'table_id': session_info['table_id'],
                        'table_number': session_info['table_number'],
                        'table_name': session_info['table_name'],
                        'created_at': session_info['created_at'].isoformat(),
                        'expires_at': session_info['expires_at'].isoformat(),
                        'time_remaining_minutes': session_info['time_remaining_minutes'],
                        'is_expiring_soon': session_info['is_expiring_soon']
                    }
                })
            else:
                return JsonResponse({
                    'success': True,
                    'has_active_session': False,
                    'session_info': None
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error interno: {str(e)}'
            })


def require_table_session(view_func):
    """
    Decorador para vistas que requieren sesión de mesa activa
    """
    def wrapper(request, *args, **kwargs):
        session_data = TableSessionManager.get_active_session(request)
        if not session_data:
            # Para peticiones AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'session_expired',
                    'message': 'Tu sesión de mesa ha expirado'
                })
            # Para peticiones normales
            else:
                from django.shortcuts import redirect
                from django.contrib import messages
                messages.warning(request, 
                    'Tu sesión de mesa ha expirado. Escanea el código QR nuevamente.')
                tenant_slug = kwargs.get('tenant_slug')
                return redirect('restaurants:home', tenant_slug=tenant_slug)
        
        # Agregar datos de sesión al request
        request.table_session = session_data
        return view_func(request, *args, **kwargs)
    
    return wrapper


# Funciones utilitarias para usar en templates y vistas

def get_table_session_context(request):
    """
    Obtener contexto de sesión de mesa para templates
    """
    session_info = TableSessionManager.get_session_info(request)
    return {
        'table_session_info': session_info,
        'has_table_session': session_info is not None
    }


def add_session_context_to_view(view_class):
    """
    Decorador de clase para agregar contexto de sesión automáticamente
    """
    original_get_context_data = view_class.get_context_data
    
    def get_context_data(self, **kwargs):
        context = original_get_context_data(self, **kwargs)
        context.update(get_table_session_context(self.request))
        return context
    
    view_class.get_context_data = get_context_data
    return view_class 