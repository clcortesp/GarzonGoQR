"""
Sistema de gestión de sesiones de mesa con seguridad y tiempo limitado
"""
import uuid
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from .models import Table, TableScanLog


class TableSessionManager:
    """
    Gestiona sesiones de mesa con expiración automática y tokens únicos
    """
    
    # Configuración de tiempos (en minutos)
    SESSION_DURATION = getattr(settings, 'TABLE_SESSION_DURATION', 60)  # 60 minutos por defecto
    INACTIVITY_TIMEOUT = getattr(settings, 'TABLE_INACTIVITY_TIMEOUT', 45)  # 45 min sin actividad
    
    @classmethod
    def create_table_session(cls, table, request):
        """
        Crear nueva sesión de mesa con token único
        """
        # Generar token único para esta sesión
        session_token = str(uuid.uuid4())
        
        # Crear registro de escaneo
        scan_log = TableScanLog.objects.create(
            table=table,
            ip_address=cls._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Datos de la sesión
        session_data = {
            'table_id': table.id,
            'table_number': table.number,
            'table_name': table.display_name,
            'scan_log_id': scan_log.id,
            'session_token': session_token,
            'created_at': timezone.now().isoformat(),
            'last_activity': timezone.now().isoformat(),
            'ip_address': cls._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
            'is_active': True
        }
        
        # Guardar en caché con expiración
        cache_key = f"table_session_{session_token}"
        cache.set(cache_key, session_data, timeout=cls.SESSION_DURATION * 60)
        
        # También en sesión del navegador como backup
        request.session['table_session'] = {
            'token': session_token,
            'table_id': table.id,
            'created_at': session_data['created_at']
        }
        
        # Incrementar contador de mesa
        table.increment_scan_count()
        
        return session_token, session_data
    
    @classmethod
    def get_active_session(cls, request):
        """
        Obtener sesión activa si es válida
        """
        browser_session = request.session.get('table_session')
        if not browser_session:
            return None
        
        session_token = browser_session.get('token')
        if not session_token:
            return None
        
        # Verificar en caché
        cache_key = f"table_session_{session_token}"
        session_data = cache.get(cache_key)
        
        if not session_data:
            # Sesión expirada
            cls.invalidate_session(request)
            return None
        
        # 🚨 VERIFICAR SI LA MESA FUE INVALIDADA POR GARZÓN
        table_id = session_data.get('table_id')
        if table_id:
            invalidation_key = f"table_invalidated_{table_id}"
            invalidation_data = cache.get(invalidation_key)
            if invalidation_data:
                # Mesa fue finalizada por garzón - invalidar sesión y marcar para redirección especial
                cls.invalidate_session(request, session_token)
                # Marcar en la sesión del navegador que debe redirigir a página especial
                request.session['redirect_to_session_closed'] = {
                    'table_id': table_id,
                    'waiter_info': invalidation_data
                }
                return None
        
        # Verificar si la sesión sigue activa
        if not session_data.get('is_active', False):
            cls.invalidate_session(request)
            return None
        
        # Verificar timeout de inactividad
        last_activity = timezone.datetime.fromisoformat(session_data['last_activity'])
        if timezone.now() - last_activity > timedelta(minutes=cls.INACTIVITY_TIMEOUT):
            cls.invalidate_session(request)
            return None
        
        # Verificar que la mesa siga activa
        try:
            table = Table.objects.get(id=session_data['table_id'])
            if not table.is_active or not table.qr_enabled:
                cls.invalidate_session(request)
                return None
        except Table.DoesNotExist:
            cls.invalidate_session(request)
            return None
        
        # Actualizar última actividad
        cls.update_activity(session_token)
        
        return session_data
    
    @classmethod
    def update_activity(cls, session_token):
        """
        Actualizar última actividad de la sesión
        """
        cache_key = f"table_session_{session_token}"
        session_data = cache.get(cache_key)
        
        if session_data:
            session_data['last_activity'] = timezone.now().isoformat()
            cache.set(cache_key, session_data, timeout=cls.SESSION_DURATION * 60)
    
    @classmethod
    def invalidate_session(cls, request, session_token=None):
        """
        Invalidar sesión de mesa
        """
        if not session_token:
            browser_session = request.session.get('table_session')
            if browser_session:
                session_token = browser_session.get('token')
        
        if session_token:
            # Marcar como inactiva en caché
            cache_key = f"table_session_{session_token}"
            session_data = cache.get(cache_key)
            if session_data:
                session_data['is_active'] = False
                session_data['ended_at'] = timezone.now().isoformat()
                cache.set(cache_key, session_data, timeout=3600)  # Mantener por 1 hora para logs
        
        # Limpiar sesión del navegador
        if 'table_session' in request.session:
            del request.session['table_session']
        
        # Limpiar sesión legacy si existe
        if 'selected_table' in request.session:
            del request.session['selected_table']
    
    @classmethod
    def extend_session(cls, request, minutes=None):
        """
        Extender tiempo de sesión (ej: cuando se hace un pedido)
        """
        if not minutes:
            minutes = cls.SESSION_DURATION
        
        session_data = cls.get_active_session(request)
        if session_data:
            session_token = session_data['session_token']
            cache_key = f"table_session_{session_token}"
            
            # Extender tiempo en caché
            cache.set(cache_key, session_data, timeout=minutes * 60)
            
            return True
        return False
    
    @classmethod
    def get_session_info(cls, request):
        """
        Obtener información completa de la sesión para mostrar al usuario
        """
        session_data = cls.get_active_session(request)
        if not session_data:
            return None
        
        created_at = timezone.datetime.fromisoformat(session_data['created_at'])
        last_activity = timezone.datetime.fromisoformat(session_data['last_activity'])
        
        # Calcular tiempo restante
        expires_at = created_at + timedelta(minutes=cls.SESSION_DURATION)
        time_remaining = expires_at - timezone.now()
        
        return {
            'table_id': session_data['table_id'],
            'table_number': session_data['table_number'],
            'table_name': session_data['table_name'],
            'created_at': created_at,
            'last_activity': last_activity,
            'expires_at': expires_at,
            'time_remaining': time_remaining,
            'time_remaining_minutes': max(0, int(time_remaining.total_seconds() / 60)),
            'is_expiring_soon': time_remaining.total_seconds() < 300,  # Menos de 5 minutos
            'session_token': session_data['session_token']
        }
    
    @classmethod
    def get_active_sessions_for_restaurant(cls, restaurant):
        """
        Obtener todas las sesiones activas para un restaurante
        """
        from django.core.cache import cache
        
        active_sessions = []
        
        # Obtener todas las mesas del restaurante
        tables = restaurant.tables.filter(is_active=True)
        
        for table in tables:
            # Buscar sesiones activas para esta mesa
            # Nota: En producción podrías usar un patrón más eficiente
            cache_pattern = f"table_session_*"
            
            # Por ahora, revisaremos las sesiones que conocemos
            # En una implementación más avanzada, podrías usar Redis SCAN
            session_info = cls._get_session_for_table(table)
            if session_info:
                active_sessions.append(session_info)
        
        return active_sessions
    
    @classmethod
    def _get_session_for_table(cls, table):
        """
        Buscar sesión activa específica para una mesa
        """
        from django.core.cache import cache
        
        # Buscar en logs recientes de escaneo para encontrar sesiones activas
        recent_scans = table.scan_logs.filter(
            scanned_at__gte=timezone.now() - timedelta(hours=2)
        ).order_by('-scanned_at')
        
        for scan in recent_scans:
            # Intentar encontrar sesión basada en la IP y tiempo
            session_data = cls._find_session_by_scan(scan)
            if session_data:
                return {
                    'table': table,
                    'session_data': session_data,
                    'scan_log': scan
                }
        
        return None
    
    @classmethod
    def _find_session_by_scan(cls, scan_log):
        """
        Encontrar sesión activa basada en scan log
        Nota: Método simplificado, en producción usarías un índice más eficiente
        """
        from django.core.cache import cache
        import re
        
        # Esto es una implementación simplificada
        # En una versión más robusta, mantendrías un índice de sesiones por mesa
        
        return None  # Por ahora retornamos None, implementaremos método más directo
    
    @classmethod
    def get_active_sessions_for_waiter(cls, waiter):
        """
        Obtener sesiones activas para las mesas asignadas a un garzón
        """
        active_sessions = []
        
        # Obtener mesas asignadas al garzón
        assigned_tables = waiter.assigned_tables.filter(is_active=True)
        
        for table in assigned_tables:
            session_info = cls._get_table_active_session(table)
            if session_info:
                active_sessions.append(session_info)
        
        return active_sessions
    
    @classmethod
    def _get_table_active_session(cls, table):
        """
        Verificar si una mesa específica tiene sesión activa
        """
        from django.core.cache import cache
        
        # Buscar en scans recientes
        recent_scan = table.scan_logs.filter(
            scanned_at__gte=timezone.now() - timedelta(minutes=cls.SESSION_DURATION + 10)
        ).order_by('-scanned_at').first()
        
        if not recent_scan:
            return None
        
        # Simular búsqueda de sesión activa
        # En implementación real, tendrías un índice mejor
        session_data = {
            'table_id': table.id,
            'table_number': table.number,
            'table_name': table.display_name,
            'scan_time': recent_scan.scanned_at,
            'ip_address': recent_scan.ip_address,
            'estimated_expires': recent_scan.scanned_at + timedelta(minutes=cls.SESSION_DURATION),
            'is_likely_active': (timezone.now() - recent_scan.scanned_at).total_seconds() < cls.SESSION_DURATION * 60
        }
        
        return session_data if session_data['is_likely_active'] else None
    
    @classmethod
    def waiter_end_table_session(cls, waiter, table, reason="finalizada_por_garzon"):
        """
        Permitir que un garzón finalice la sesión de una mesa
        """
        # Verificar que el garzón tiene autoridad sobre la mesa
        if table.assigned_waiter != waiter:
            return False, "No tienes autoridad sobre esta mesa"
        
        # 🔥 INVALIDAR TODAS LAS SESIONES ACTIVAS DE ESTA MESA
        from django.core.cache import cache
        sessions_ended = 0
        
        # 1. Buscar sesiones activas por escaneos recientes
        recent_scans = table.scan_logs.filter(
            scanned_at__gte=timezone.now() - timedelta(minutes=cls.SESSION_DURATION + 10)
        )
        
        # 2. El método MÁS SEGURO: Encontrar sesiones por tokens específicos de esta mesa
        # Las sesiones se almacenan como: "table_session_{uuid_token}"
        # Necesitamos encontrar los tokens activos relacionados con esta mesa específica
        
        # Obtener tokens de sesiones activas desde la base de datos
        for scan in recent_scans:
            # Las sesiones están en caché como "table_session_{token}"
            # Buscamos todas las claves que empiecen con "table_session_"
            try:
                from django.core.cache.backends.base import InvalidCacheBackendError
                cache_keys = cache._cache.get_client().keys("table_session_*")
                
                for key in cache_keys:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    session_data = cache.get(key_str)
                    
                    # Verificar si esta sesión pertenece a NUESTRA mesa específica
                    if session_data and session_data.get('table_id') == table.id:
                        # Esta sesión ES de nuestra mesa - eliminarla
                        cache.delete(key_str)
                        sessions_ended += 1
                        
            except (AttributeError, InvalidCacheBackendError):
                # Fallback si no podemos acceder a Redis directamente
                # En este caso, el marcador de invalidación será suficiente
                break
        
        # 4. Marcar mesa como "limpiada" por garzón en la BD
        from .models import TableScanLog
        TableScanLog.objects.create(
            table=table,
            scanned_at=timezone.now(),
            ip_address="WAITER_CLEANUP",
            user_agent=f"Finalizada por garzón: {waiter.full_name} - {reason} - {sessions_ended} sesiones invalidadas",
            resulted_in_order=False
        )
        
        # 5. Crear marcador especial para invalidar futuras validaciones
        invalidation_key = f"table_invalidated_{table.id}"
        cache.set(invalidation_key, {
            'waiter_id': waiter.id,
            'waiter_name': waiter.full_name,
            'reason': reason,
            'timestamp': timezone.now().isoformat(),
            'sessions_ended': sessions_ended,
            'table_number': table.number,
            'table_name': table.display_name,
            'restaurant_name': table.restaurant.name
        }, timeout=3600)  # Válido por 1 hora
        
        return True, f"Sesión de {table.display_name} finalizada por garzón ({sessions_ended} sesiones cerradas)"
    
    @classmethod
    def _get_client_ip(cls, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TableSessionMiddleware:
    """
    Middleware para validar sesiones de mesa automáticamente
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Validar sesión antes de cada request en rutas que requieren sesión
        if request.path.startswith('/menu/') or request.path.startswith('/orders/') or 'cart' in request.path:
            from django.shortcuts import redirect
            from django.core.cache import cache
            
            # Verificar si hay información en la sesión del navegador
            browser_session = request.session.get('table_session')
            table_id = None
            if browser_session:
                table_id = browser_session.get('table_id')
            
            # VERIFICAR SI LA MESA FUE INVALIDADA POR GARZÓN ANTES de validar sesión
            if table_id:
                invalidation_key = f"table_invalidated_{table_id}"
                invalidation_data = cache.get(invalidation_key)
                if invalidation_data:
                    # Sesión fue cerrada por garzón - redirigir a página especial
                    try:
                        tenant_slug = request.resolver_match.kwargs.get('tenant_slug')
                        if tenant_slug:
                            return redirect(f'/{tenant_slug}/session-closed/?table_id={table_id}')
                    except:
                        pass
            
            # Obtener sesión activa (esto también detecta invalidaciones)
            session_data = TableSessionManager.get_active_session(request)
            request.table_session = session_data
            
            # Si no hay sesión válida y estamos en ruta protegida, redirigir a home
            if not session_data and request.method == 'GET':
                from django.contrib import messages
                try:
                    tenant_slug = request.resolver_match.kwargs.get('tenant_slug')
                    if tenant_slug:
                        messages.warning(request, 
                            'Tu sesión de mesa ha expirado. Por favor, escanea el código QR nuevamente.')
                        return redirect(f'/{tenant_slug}/')
                except:
                    pass
        
        response = self.get_response(request)
        return response


class TableSessionDecorator:
    """
    Decorador para vistas que requieren sesión de mesa válida
    """
    
    @staticmethod
    def require_active_session(view_func):
        """
        Decorador que requiere sesión de mesa activa
        """
        def wrapper(request, *args, **kwargs):
            from django.shortcuts import redirect
            from django.contrib import messages
            from django.core.cache import cache
            
            # Verificar si hay información en la sesión del navegador
            browser_session = request.session.get('table_session')
            table_id = None
            if browser_session:
                table_id = browser_session.get('table_id')
            
            # Verificar si la mesa fue invalidada por garzón ANTES de validar sesión
            if table_id:
                invalidation_key = f"table_invalidated_{table_id}"
                invalidation_data = cache.get(invalidation_key)
                if invalidation_data:
                    # Sesión fue cerrada por garzón - redirigir a página especial
                    tenant_slug = kwargs.get('tenant_slug') or request.resolver_match.kwargs.get('tenant_slug')
                    return redirect(f'/{tenant_slug}/session-closed/?table_id={table_id}')
            
            session_data = TableSessionManager.get_active_session(request)
            if not session_data:
                messages.warning(request, 
                    'Tu sesión de mesa ha expirado. Por favor, escanea el código QR nuevamente.')
                tenant_slug = kwargs.get('tenant_slug') or request.resolver_match.kwargs.get('tenant_slug')
                return redirect('restaurants:home', tenant_slug=tenant_slug)
            
            # Agregar datos de sesión al request
            request.table_session = session_data
            return view_func(request, *args, **kwargs)
        
        return wrapper 