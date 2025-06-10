"""
Middleware para gestión de empleados por rol
Detecta el tipo de empleado y proporciona contexto específico
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout
from .models import KitchenStaff, BarStaff, WaiterStaff, Waiter


class StaffRoleMiddleware:
    """
    Middleware que detecta el tipo de empleado y proporciona contexto
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Procesar antes de la vista
        self.process_request(request)
        
        response = self.get_response(request)
        
        return response
    
    def process_request(self, request):
        """
        Detectar tipo de empleado y agregar al contexto de request
        """
        # Solo procesar usuarios autenticados
        if not request.user.is_authenticated:
            return
        
        # Skip para superusers y admin
        if request.user.is_superuser or request.user.is_staff:
            request.staff_role = 'admin'
            request.staff_member = None
            return
        
        # Obtener tenant si existe (del TenantMiddleware)
        tenant = getattr(request, 'tenant', None)
        restaurant = getattr(request, 'restaurant', None)
        
        if not restaurant:
            return
        
        # Detectar tipo de empleado
        print(f"🔍 StaffRoleMiddleware checking user: {request.user.username}")
        staff_member = None
        staff_role = None
        
        # Verificar KitchenStaff
        try:
            staff_member = KitchenStaff.objects.get(user=request.user, restaurant=restaurant)
            staff_role = 'kitchen'
        except KitchenStaff.DoesNotExist:
            pass
        
        # Verificar BarStaff
        if not staff_member:
            try:
                staff_member = BarStaff.objects.get(user=request.user, restaurant=restaurant)
                staff_role = 'bar'
            except BarStaff.DoesNotExist:
                pass
        
        # Verificar WaiterStaff
        if not staff_member:
            try:
                staff_member = WaiterStaff.objects.get(user=request.user, restaurant=restaurant)
                staff_role = 'waiter_new'
            except WaiterStaff.DoesNotExist:
                pass
        
        # Verificar Waiter original (compatibilidad)
        if not staff_member:
            try:
                staff_member = Waiter.objects.get(user=request.user, restaurant=restaurant)
                staff_role = 'waiter'
            except Waiter.DoesNotExist:
                pass
        
        # Agregar información al request
        request.staff_member = staff_member
        request.staff_role = staff_role
        
        if staff_member:
            print(f"✅ Found staff: {staff_member.full_name} with role: {staff_role}")
        else:
            print(f"❌ No staff member found for user: {request.user.username}")
        
        # Verificar acceso a rutas protegidas
        self.check_role_access(request)
    
    def check_role_access(self, request):
        """
        Verificar que el empleado acceda solo a sus rutas permitidas
        """
        if not request.staff_member:
            return
        
        path = request.path
        role = request.staff_role
        tenant = getattr(request, 'tenant', None)
        tenant_slug = tenant.slug if tenant else ''
        
        # Definir rutas permitidas por rol
        role_routes = {
            'kitchen': [
                f'/{tenant_slug}/kitchen/',
                f'/{tenant_slug}/api/kitchen/',
            ],
            'bar': [
                f'/{tenant_slug}/bar/',
                f'/{tenant_slug}/api/bar/',
            ],
            'waiter': [
                f'/{tenant_slug}/waiter/',
                f'/{tenant_slug}/api/waiter/',
                f'/{tenant_slug}/tables/',
            ],
            'waiter_new': [
                f'/{tenant_slug}/waiter/',
                f'/{tenant_slug}/api/waiter/',
                f'/{tenant_slug}/tables/',
            ]
        }
        
        # Rutas comunes permitidas para todos
        common_routes = [
            '/logout/',
            '/api/auth/',
            '/static/',
            '/media/',
            f'/{tenant_slug}/menu/',  # Para ver menú
        ]
        
        # Verificar si la ruta está permitida
        allowed_routes = role_routes.get(role, []) + common_routes
        
        # Verificar acceso
        is_allowed = any(path.startswith(route) for route in allowed_routes)
        
        if not is_allowed and not self.is_protected_route(path):
            # Redireccionar a dashboard apropiado
            self.redirect_to_role_dashboard(request, role, tenant_slug)
    
    def is_protected_route(self, path):
        """
        Verificar si es una ruta que no necesita verificación de rol
        """
        unprotected_patterns = [
            '/admin/',
            '/accounts/',
            '/api/public/',
        ]
        
        return any(path.startswith(pattern) for pattern in unprotected_patterns)
    
    def redirect_to_role_dashboard(self, request, role, tenant_slug):
        """
        Redireccionar al dashboard correcto según el rol
        """
        if not tenant_slug:
            return
        
        # Mapeo de roles a URLs de dashboard
        dashboard_urls = {
            'kitchen': f'/{tenant_slug}/kitchen/',
            'bar': f'/{tenant_slug}/bar/',
            'waiter': f'/{tenant_slug}/waiter/',
            'waiter_new': f'/{tenant_slug}/waiter/',
        }
        
        target_url = dashboard_urls.get(role)
        
        if target_url and request.path != target_url:
            # Solo redireccionar si no está ya en la ruta correcta
            return redirect(target_url)


class StaffContextMiddleware:
    """
    Middleware que agrega contexto específico del empleado a todas las vistas
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Agregar contexto antes de procesar
        self.add_staff_context(request)
        
        response = self.get_response(request)
        
        return response
    
    def add_staff_context(self, request):
        """
        Agregar información contextual del empleado
        """
        staff_member = getattr(request, 'staff_member', None)
        staff_role = getattr(request, 'staff_role', None)
        
        if not staff_member:
            return
        
        # Contexto específico por rol
        tenant = getattr(request, 'tenant', None)
        tenant_slug = tenant.slug if tenant else ''
        
        if staff_role == 'kitchen':
            request.staff_context = {
                'role': 'kitchen',
                'role_display': 'Cocina',
                'icon': '👨‍🍳',
                'color': '#dc3545',
                'dashboard_url': f"/{tenant_slug}/kitchen/",
                'can_modify_prep_time': staff_member.can_modify_prep_time,
                'priority_level': staff_member.priority_level,
                'specialties': staff_member.specialties,
            }
        
        elif staff_role == 'bar':
            request.staff_context = {
                'role': 'bar',
                'role_display': 'Bar',
                'icon': '🍸',
                'color': '#0d6efd',
                'dashboard_url': f"/{tenant_slug}/bar/",
                'can_serve_alcohol': staff_member.can_serve_alcohol,
                'has_bartender_license': staff_member.has_bartender_license,
                'drink_specialties': staff_member.drink_specialties,
            }
        
        elif staff_role in ['waiter', 'waiter_new']:
            request.staff_context = {
                'role': 'waiter',
                'role_display': 'Garzón',
                'icon': '🍽️',
                'color': '#fd7e14',
                'dashboard_url': f"/{tenant_slug}/waiter/",
                'assigned_tables_count': getattr(staff_member, 'assigned_tables_count', 0),
                'can_take_orders': getattr(staff_member, 'can_take_orders', True),
            }
        
        # Información común
        if hasattr(request, 'staff_context'):
            request.staff_context.update({
                'full_name': staff_member.full_name,
                'status': staff_member.status,
                'is_available': staff_member.is_available,
                'is_working_hours': staff_member.is_working_hours,
                'employee_id': staff_member.employee_id,
                'last_active': staff_member.last_active,
            })


def get_staff_member_by_user(user, restaurant):
    """
    Función utilitaria para obtener el empleado según el usuario
    """
    # Intentar en orden de prioridad
    staff_models = [
        (KitchenStaff, 'kitchen'),
        (BarStaff, 'bar'), 
        (WaiterStaff, 'waiter_new'),
        (Waiter, 'waiter'),
    ]
    
    for model_class, role in staff_models:
        try:
            staff_member = model_class.objects.get(user=user, restaurant=restaurant)
            return staff_member, role
        except model_class.DoesNotExist:
            continue
    
    return None, None


def staff_required_by_role(*allowed_roles):
    """
    Decorador para vistas que requieren roles específicos de empleados
    
    Uso:
    @staff_required_by_role('kitchen', 'bar')
    def my_view(request):
        ...
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            staff_role = getattr(request, 'staff_role', None)
            
            if not staff_role or staff_role not in allowed_roles:
                # Redireccionar a página de acceso denegado o dashboard correcto
                return redirect('/')  # O página de error personalizada
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator 