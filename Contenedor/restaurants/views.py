from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, RedirectView
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.urls import reverse
import qrcode
from io import BytesIO
import base64
from .models import Tenant, Restaurant, Table, TableScanLog
from .middleware import get_current_tenant, get_current_restaurant

# Create your views here.

class TenantMixin:
    """Mixin para views que requieren contexto de tenant"""
    
    def get_context_data(self, **kwargs):
        from .models import Waiter, KitchenStaff, BarStaff, WaiterStaff
        
        context = super().get_context_data(**kwargs)
        
        # Verificar el tipo de empleado si está autenticado
        user_is_waiter = False
        user_is_kitchen = False
        user_is_bar = False
        
        if self.request.user.is_authenticated:
            restaurant = get_current_restaurant(self.request)
            
            # Verificar garzón original
            try:
                Waiter.objects.get(restaurant=restaurant, user=self.request.user)
                user_is_waiter = True
            except Waiter.DoesNotExist:
                pass
            
            # Verificar nuevo garzón
            if not user_is_waiter:
                try:
                    WaiterStaff.objects.get(restaurant=restaurant, user=self.request.user)
                    user_is_waiter = True
                except WaiterStaff.DoesNotExist:
                    pass
            
            # Verificar personal de cocina
            try:
                KitchenStaff.objects.get(restaurant=restaurant, user=self.request.user)
                user_is_kitchen = True
            except KitchenStaff.DoesNotExist:
                pass
            
            # Verificar personal de bar
            try:
                BarStaff.objects.get(restaurant=restaurant, user=self.request.user)
                user_is_bar = True
            except BarStaff.DoesNotExist:
                pass
        
        context.update({
            'tenant': get_current_tenant(self.request),
            'restaurant': get_current_restaurant(self.request),
            'user_is_waiter': user_is_waiter,
            'user_is_kitchen': user_is_kitchen,
            'user_is_bar': user_is_bar,
        })
        return context


class TenantLoginView(TenantMixin, LoginView):
    """Vista de login específica para el tenant"""
    template_name = 'restaurants/auth/login.html'
    
    def get_success_url(self):
        from .models import Waiter, KitchenStaff, BarStaff, WaiterStaff
        
        user = self.request.user
        restaurant = self.request.restaurant
        tenant_slug = self.request.tenant.slug
        
        # Verificar si el usuario es personal de cocina
        try:
            KitchenStaff.objects.get(restaurant=restaurant, user=user)
            return f'/{tenant_slug}/kitchen/'
        except KitchenStaff.DoesNotExist:
            pass
        
        # Verificar si el usuario es personal de bar
        try:
            BarStaff.objects.get(restaurant=restaurant, user=user)
            return f'/{tenant_slug}/bar/'
        except BarStaff.DoesNotExist:
            pass
        
        # Verificar si el usuario es un garzón (nuevo modelo)
        try:
            WaiterStaff.objects.get(restaurant=restaurant, user=user)
            return f'/{tenant_slug}/waiter/'
        except WaiterStaff.DoesNotExist:
            pass
        
        # Verificar si el usuario es un garzón (modelo original)
        try:
            Waiter.objects.get(restaurant=restaurant, user=user)
            return f'/{tenant_slug}/waiter/'
        except Waiter.DoesNotExist:
            pass
        
        # Verificar si es owner/admin del restaurante
        if (user == restaurant.owner or user.is_staff or user.is_superuser):
            return f'/{tenant_slug}/admin/'
        
        # Usuario sin permisos específicos, redirigir al home
        return f'/{tenant_slug}/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener el rol solicitado del parámetro de consulta
        requested_role = self.request.GET.get('role', 'general')
        
        role_info = {
            'admin': {'name': 'Administración', 'icon': '👑', 'description': 'Panel de administración'},
            'kitchen': {'name': 'Cocina', 'icon': '👨‍🍳', 'description': 'Acceso a cocina'},
            'bar': {'name': 'Bar', 'icon': '🍹', 'description': 'Acceso a bar'},
            'waiter': {'name': 'Servicio', 'icon': '🫱', 'description': 'Acceso a servicio'},
            'general': {'name': 'Empleado', 'icon': '🔑', 'description': 'Acceso general'},
        }
        
        current_role = role_info.get(requested_role, role_info['general'])
        
        context.update({
            'page_title': f'Iniciar Sesión - {current_role["name"]} - {self.request.restaurant.name}',
            'role_info': current_role,
            'requested_role': requested_role,
        })
        return context


class StaffLoginPageView(TenantMixin, TemplateView):
    """Vista para la página de selección de rol de empleados"""
    template_name = 'restaurants/auth/staff_login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': f'Acceso de Empleados - {self.request.restaurant.name}',
        })
        return context


class TenantLogoutView(TenantMixin, LogoutView):
    """Vista de logout específica para el tenant"""
    template_name = 'restaurants/auth/logout.html'
    http_method_names = ['get', 'post']  # Permitir ambos métodos
    
    def get_next_page(self):
        # Redirigir a la página principal del tenant después del logout
        try:
            return f'/{self.request.tenant.slug}/'
        except AttributeError:
            # Fallback si no hay tenant
            return '/'
    
    def get(self, request, *args, **kwargs):
        """Manejar peticiones GET realizando logout inmediatamente"""
        from django.contrib.auth import logout
        logout(request)
        # Limpiar mensajes de sesión si existen
        if hasattr(request, 'session'):
            messages.success(request, 'Has cerrado sesión exitosamente.')
        return redirect(self.get_next_page())
    
    def post(self, request, *args, **kwargs):
        """Manejar peticiones POST con el comportamiento estándar de LogoutView"""
        try:
            return super().post(request, *args, **kwargs)
        except Exception as e:
            # Fallback a logout manual si hay problemas
            from django.contrib.auth import logout
            logout(request)
            return redirect(self.get_next_page())
    
    def dispatch(self, request, *args, **kwargs):
        """Manejo seguro del dispatch"""
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            # Fallback último recurso
            from django.contrib.auth import logout
            logout(request)
            return redirect('/')


def simple_logout_view(request, tenant_slug):
    """Vista simple de logout con redirect directo"""
    from django.contrib.auth import logout
    from django.shortcuts import redirect
    
    logout(request)
    return redirect('restaurants:home', tenant_slug=tenant_slug)


def test_logout_view(request, tenant_slug):
    """Vista de test para probar logout"""
    from django.shortcuts import render
    
    return render(request, 'test_logout.html', {
        'tenant_slug': tenant_slug
    })


def test_links_view(request, tenant_slug):
    """Vista de test para probar enlaces"""
    from django.shortcuts import render
    
    return render(request, 'test_links.html', {
        'tenant_slug': tenant_slug
    })


class TenantHomeView(TenantMixin, TemplateView):
    """Página principal del restaurante"""
    template_name = 'restaurants/home.html'
    
    def dispatch(self, request, tenant_slug=None, *args, **kwargs):
        print(f"🏠 TenantHomeView.dispatch() - URL: {request.path}")
        print(f"🏠 TenantHomeView.dispatch() - Tenant: {getattr(request, 'tenant', 'NO_TENANT')}")
        print(f"🏠 TenantHomeView.dispatch() - tenant_slug param: {tenant_slug}")
        print(f"🏠 TenantHomeView.dispatch() - Args: {args}, Kwargs: {kwargs}")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(f"🏠 TenantHomeView.get_context_data() ejecutándose")
        context.update({
            'page_title': f'Bienvenido a {self.request.restaurant.name}',
        })
        return context


class MenuView(TenantMixin, TemplateView):
    """Vista del menú del restaurante"""
    template_name = 'restaurants/menu.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': f'Menú - {self.request.restaurant.name}',
        })
        return context


class CartView(TenantMixin, TemplateView):
    """Vista del carrito de compras"""
    template_name = 'restaurants/cart.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Carrito de Compras',
        })
        return context


class CheckoutView(TenantMixin, TemplateView):
    """Vista del proceso de pago"""
    template_name = 'restaurants/checkout.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Finalizar Pedido',
        })
        return context


class QRScanView(TenantMixin, TemplateView):
    """Vista para QR escaneado desde mesa"""
    template_name = 'restaurants/qr_scan.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qr_token = kwargs.get('qr_token')
        context.update({
            'page_title': 'Mesa Escaneada',
            'qr_token': qr_token,
            'welcome_message': f'¡Bienvenido a {self.request.restaurant.name}!',
        })
        return context


class DashboardRedirectView(LoginRequiredMixin, TenantMixin, RedirectView):
    """Redirigir al dashboard funcional de pedidos"""
    def get_redirect_url(self, *args, **kwargs):
        tenant_slug = self.request.tenant.slug
        return f'/{tenant_slug}/orders/dashboard/'


class OrdersRedirectView(LoginRequiredMixin, TenantMixin, RedirectView):
    """Redirigir al dashboard de pedidos"""
    def get_redirect_url(self, *args, **kwargs):
        tenant_slug = self.request.tenant.slug
        return f'/{tenant_slug}/orders/dashboard/'


class MenuManagementView(LoginRequiredMixin, TenantMixin, TemplateView):
    """Gestión del menú"""
    template_name = 'restaurants/dashboard/menu.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Gestión del Menú',
            'is_dashboard': True,
        })
        return context


class TenantSettingsView(LoginRequiredMixin, TenantMixin, TemplateView):
    """Configuración del tenant"""
    template_name = 'restaurants/settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Configuración',
        })
        return context


# API Views para testing
def tenant_info_api(request, tenant_slug=None):
    """API para obtener información del tenant actual"""
    if hasattr(request, 'tenant'):
        return JsonResponse({
            'tenant_name': request.tenant.name,
            'tenant_slug': request.tenant.slug,
            'restaurant_name': request.restaurant.name,
            'primary_color': request.tenant.primary_color,
            'status': request.tenant.status,
        })
    return JsonResponse({'error': 'No tenant found'}, status=404)


# Vista de test SÚPER simple
def ultra_simple_view(request, tenant_slug=None):
    """Vista de test súper básica"""
    print(f"🟢🟢🟢 ULTRA_SIMPLE_VIEW ejecutándose!!!")
    print(f"🟢 Tenant slug recibido: {tenant_slug}")
    print(f"🟢 Tenant en request: {getattr(request, 'tenant', 'NO_TENANT')}")
    return HttpResponse("🟢 ULTRA SIMPLE VIEW FUNCIONANDO 🟢")

# Vista de test completamente nueva
def brand_new_test_view(request, tenant_slug=None):
    """Vista completamente nueva para evitar caché"""
    print(f"🟦🟦🟦 BRAND_NEW_TEST_VIEW ejecutándose!!!")
    print(f"🟦 Tenant slug recibido: {tenant_slug}")
    print(f"🟦 Tenant en request: {getattr(request, 'tenant', 'NO_TENANT')}")
    return HttpResponse("🟦 BRAND NEW TEST VIEW FUNCIONANDO 🟦")

# Vista de test simple
def simple_test_view(request, tenant_slug=None):
    """Vista de test súper simple"""
    try:
        print(f"🟢 SIMPLE_TEST_VIEW ejecutándose - URL: {request.path}")
        print(f"🟢 SIMPLE_TEST_VIEW - Tenant: {getattr(request, 'tenant', 'NO_TENANT')}")
        print(f"🟢 SIMPLE_TEST_VIEW - Args: {tenant_slug}")
        
        html = f"""
        <html>
        <head><title>Test Simple</title></head>
        <body>
            <h1>🟢 VISTA DE TEST SIMPLE FUNCIONANDO</h1>
            <p>URL: {request.path}</p>
            <p>Tenant: {getattr(request, 'tenant', 'NO_TENANT')}</p>
            <p>Args: {tenant_slug}</p>
            <p>Esta vista funciona correctamente.</p>
        </body>
        </html>
        """
        return HttpResponse(html)
    except Exception as e:
        print(f"❌ ERROR en simple_test_view: {e}")
        import traceback
        traceback.print_exc()
        return HttpResponse(f"ERROR: {e}")








def home(request):
    """
    Página principal del sitio
    """
    context = {
        'title': 'GarzónGo QR - Sistema de Pedidos Digital'
    }
    return render(request, 'restaurants/home.html', context)


def restaurant_home(request, tenant_slug):
    """
    Página principal de un restaurante específico
    """
    try:
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        restaurant = tenant.restaurant
        
        context = {
            'restaurant': restaurant,
            'tenant': tenant,
        }
        
        return render(request, 'restaurants/restaurant_home.html', context)
        
    except Exception as e:
        raise Http404("Restaurante no encontrado")


def table_qr_scan(request, tenant_slug, table_uuid):
    """
    Vista que se ejecuta cuando alguien escanea un código QR de mesa
    """
    try:
        from .table_session_manager import TableSessionManager
        
        # Obtener tenant y restaurant
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        restaurant = tenant.restaurant
        
        # Obtener mesa por UUID
        table = get_object_or_404(Table, qr_code_uuid=table_uuid, restaurant=restaurant)
        
        # Verificar que la mesa esté activa
        if not table.is_active or not table.qr_enabled:
            messages.warning(request, f'La mesa {table.number} no está disponible actualmente.')
            return redirect('restaurants:home', tenant_slug=tenant_slug)
        
        # Verificar si ya hay una sesión activa para esta mesa desde otra IP
        existing_session = TableSessionManager.get_active_session(request)
        if existing_session and existing_session['table_id'] == table.id:
            # Renovar sesión existente
            TableSessionManager.extend_session(request)
            messages.info(request, f'Sesión renovada para {table.display_name}.')
        else:
            # Invalidar sesión anterior si existe
            if existing_session:
                TableSessionManager.invalidate_session(request)
            
            # Crear nueva sesión segura
            session_token, session_data = TableSessionManager.create_table_session(table, request)
            
            duration_minutes = TableSessionManager.SESSION_DURATION
            messages.success(request, 
                f'¡Bienvenido a {table.display_name}! Tu sesión estará activa por {duration_minutes} minutos.')
        
        # Redirigir al menú del restaurante
        return redirect(f'/{tenant_slug}/menu/')
        
    except Exception as e:
        messages.error(request, 'Error al procesar el código QR. Por favor inténtalo de nuevo.')
        return redirect('restaurants:home', tenant_slug=tenant_slug)


@login_required
def tables_management(request, tenant_slug):
    """
    Panel de gestión de mesas para el restaurante
    """
    try:
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        restaurant = tenant.restaurant
        
        # Verificar permisos
        if not (request.user.is_superuser or restaurant.owner == request.user):
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('restaurants:restaurant_home', tenant_slug=tenant_slug)
        
        # Obtener todas las mesas
        tables = Table.objects.filter(restaurant=restaurant).order_by('number')
        
        # Estadísticas generales
        stats = {
            'total_tables': tables.count(),
            'active_tables': tables.filter(is_active=True).count(),
            'qr_enabled_tables': tables.filter(qr_enabled=True).count(),
            'total_scans_today': TableScanLog.objects.filter(
                table__restaurant=restaurant,
                scanned_at__date=timezone.now().date()
            ).count(),
            'total_scans_all_time': sum(table.total_scans for table in tables),
            'total_orders_from_qr': sum(table.total_orders for table in tables)
        }
        
        context = {
            'restaurant': restaurant,
            'tenant': tenant,
            'tables': tables,
            'stats': stats
        }
        
        return render(request, 'restaurants/tables_management.html', context)
        
    except Exception as e:
        messages.error(request, 'Error al cargar el panel de mesas.')
        return redirect('restaurants:restaurant_home', tenant_slug=tenant_slug)


@login_required
@require_http_methods(["POST"])
def create_table(request, tenant_slug):
    """
    Crear una nueva mesa
    """
    try:
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        restaurant = tenant.restaurant
        
        # Verificar permisos
        if not (request.user.is_superuser or restaurant.owner == request.user):
            return JsonResponse({'success': False, 'error': 'Sin permisos'})
        
        # Obtener datos del formulario
        number = request.POST.get('number', '').strip()
        name = request.POST.get('name', '').strip()
        capacity = int(request.POST.get('capacity', 4))
        location = request.POST.get('location', '').strip()
        
        # Validaciones
        if not number:
            return JsonResponse({'success': False, 'error': 'El número de mesa es obligatorio'})
        
        # Verificar que no exista otra mesa con el mismo número
        if Table.objects.filter(restaurant=restaurant, number=number).exists():
            return JsonResponse({'success': False, 'error': f'Ya existe una mesa con el número {number}'})
        
        # Crear la mesa
        table = Table.objects.create(
            restaurant=restaurant,
            number=number,
            name=name,
            capacity=capacity,
            location=location
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Mesa {number} creada exitosamente',
            'table': {
                'id': table.id,
                'number': table.number,
                'name': table.display_name,
                'capacity': table.capacity,
                'location': table.location,
                'qr_url': table.qr_url,
                'is_active': table.is_active,
                'qr_enabled': table.qr_enabled
            }
        })
        
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Capacidad debe ser un número válido'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al crear mesa: {str(e)}'})


@login_required
def generate_table_qr(request, tenant_slug, table_id):
    """
    Generar código QR para una mesa específica
    """
    try:
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        restaurant = tenant.restaurant
        table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
        
        # Verificar permisos
        if not (request.user.is_superuser or restaurant.owner == request.user):
            return HttpResponse('Sin permisos', status=403)
        
        # Generar código QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Usar URL dinámica basada en el request
        qr_url = table.get_full_qr_url(request)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Crear imagen QR
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir a bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Retornar como imagen
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="qr_mesa_{table.number}.png"'
        
        return response
        
    except Exception as e:
        return HttpResponse(f'Error al generar QR: {str(e)}', status=500)


@login_required
def table_qr_preview(request, tenant_slug, table_id):
    """
    Vista previa del código QR de una mesa
    """
    try:
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        restaurant = tenant.restaurant
        table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
        
        # Verificar permisos
        if not (request.user.is_superuser or restaurant.owner == request.user):
            messages.error(request, 'Sin permisos')
            return redirect('restaurants:tables_management', tenant_slug=tenant_slug)
        
        # Generar código QR como base64 para mostrar en HTML
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=4,
        )
        
        # Usar URL dinámica basada en el request
        qr_url = table.get_full_qr_url(request)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        context = {
            'restaurant': restaurant,
            'tenant': tenant,
            'table': table,
            'qr_image': img_str,
            'qr_url': qr_url  # URL dinámica ya calculada
        }
        
        return render(request, 'restaurants/table_qr_preview.html', context)
        
    except Exception as e:
        messages.error(request, f'Error al generar vista previa: {str(e)}')
        return redirect('restaurants:tables_management', tenant_slug=tenant_slug)


def get_client_ip(request):
    """Obtener IP del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def session_closed_by_waiter(request, tenant_slug):
    """
    Página especial para cuando el garzón cierra la sesión del cliente
    """
    restaurant = request.restaurant
    
    # Obtener información del garzón que cerró la sesión (si está disponible)
    waiter_info = None
    table_info = None
    
    # Verificar si hay información sobre quién cerró la sesión
    table_id = request.GET.get('table_id')
    if table_id:
        from django.core.cache import cache
        try:
            table = Table.objects.get(id=table_id, restaurant=restaurant)
            table_info = {
                'number': table.number,
                'name': table.name or f"Mesa {table.number}"
            }
        except Table.DoesNotExist:
            pass
            
        invalidation_key = f"table_invalidated_{table_id}"
        invalidation_data = cache.get(invalidation_key)
        
        if invalidation_data:
            waiter_info = {
                'name': invalidation_data.get('waiter_name', 'Nuestro equipo'),
                'reason': invalidation_data.get('reason', 'Finalización de servicio'),
                'timestamp': invalidation_data.get('timestamp'),
                'sessions_ended': invalidation_data.get('sessions_ended', 0)
            }
    
    # Limpiar cualquier sesión residual
    if 'table_session' in request.session:
        del request.session['table_session']
    if 'selected_table' in request.session:
        del request.session['selected_table']
    
    context = {
        'restaurant': restaurant,
        'waiter_info': waiter_info,
        'table_info': table_info,
        'page_title': f'Sesión Finalizada - {restaurant.name}',
        'show_hero': False,
    }
    
    return render(request, 'restaurants/session_closed.html', context)
