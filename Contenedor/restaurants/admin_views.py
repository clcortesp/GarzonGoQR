# restaurants/admin_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.urls import reverse_lazy, reverse
from datetime import timedelta, datetime
import qrcode
from io import BytesIO
import base64

from .models import Restaurant, Table, WaiterNotification, KitchenStaff, BarStaff, WaiterStaff
from menu.models import MenuItem, MenuCategory, MenuVariant, MenuAddon
from orders.models import Order, OrderItem
from django.contrib.auth.models import User


# ============================================================================
# UTILIDADES DE LOGOUT
# ============================================================================

@login_required
def admin_logout_view(request, tenant_slug):
    """Vista de logout específica para el admin del restaurante"""
    from django.contrib.auth import logout
    from django.shortcuts import redirect
    
    logout(request)
    messages.success(request, 'Has cerrado sesión del panel de administración.')
    return redirect('restaurants:home', tenant_slug=tenant_slug)


# ============================================================================
# MIXIN Y DECORADORES
# ============================================================================

class RestaurantAdminMixin(LoginRequiredMixin):
    """Mixin para vistas de administración del restaurante"""
    
    def dispatch(self, request, *args, **kwargs):
        # Verificar que el usuario sea el owner del restaurante
        restaurant = request.restaurant
        if not (request.user.is_superuser or restaurant.owner == request.user):
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('restaurants:home', tenant_slug=request.tenant.slug)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'restaurant': self.request.restaurant,
            'tenant': self.request.tenant,
            'is_admin_dashboard': True,
        })
        return context


def restaurant_admin_required(view_func):
    """Decorador para verificar permisos de administrador del restaurante"""
    @login_required
    def wrapper(request, *args, **kwargs):
        restaurant = request.restaurant
        if not (request.user.is_superuser or restaurant.owner == request.user):
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('restaurants:home', tenant_slug=request.tenant.slug)
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================================================
# DASHBOARD PRINCIPAL
# ============================================================================

class RestaurantAdminDashboard(RestaurantAdminMixin, TemplateView):
    """Dashboard principal para administradores del restaurante"""
    template_name = 'restaurants/admin/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.request.restaurant
        
        # Obtener configuración de QR actual
        sample_table = restaurant.tables.first()
        current_qr_config = {
            'has_custom_domain': bool(restaurant.tenant.domain),
            'custom_domain': restaurant.tenant.domain,
            'sample_qr_url': sample_table.get_full_qr_url(self.request) if sample_table else None,
            'detection_method': self._get_qr_detection_method(sample_table)
        }
        
        # Estadísticas generales
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Pedidos
        orders_today = Order.objects.filter(restaurant=restaurant, created_at__date=today)
        orders_week = Order.objects.filter(restaurant=restaurant, created_at__date__gte=week_ago)
        orders_month = Order.objects.filter(restaurant=restaurant, created_at__date__gte=month_ago)
        
        # Ventas
        sales_today = orders_today.filter(status__in=['delivered', 'ready']).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        sales_week = orders_week.filter(status__in=['delivered', 'ready']).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        sales_month = orders_month.filter(status__in=['delivered', 'ready']).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Pedidos pendientes
        pending_orders = Order.objects.filter(
            restaurant=restaurant,
            status__in=['pending', 'confirmed', 'preparing']
        ).order_by('-created_at')[:10]
        
        # Productos más vendidos
        top_products = OrderItem.objects.filter(
            order__restaurant=restaurant,
            order__created_at__date__gte=month_ago
        ).values(
            'menu_item__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_quantity')[:10]
        
        # Personal activo usando los nombres correctos de relacionados Django
        
        # KitchenStaff, BarStaff y WaiterStaff heredan de RestaurantEmployee que tiene restaurant = ForeignKey(Restaurant)
        active_kitchen_staff = KitchenStaff.objects.filter(restaurant=restaurant, status='active')
        active_bar_staff = BarStaff.objects.filter(restaurant=restaurant, status='active')
        active_waiter_staff = WaiterStaff.objects.filter(restaurant=restaurant, status='active')
        
        # El sistema ahora usa solo WaiterStaff para meseros
        total_active_staff = active_kitchen_staff.count() + active_bar_staff.count() + active_waiter_staff.count()
        
        # Mesas con problemas
        # Mesas sin mesero asignado (nuevo sistema)
        tables_without_waiter = restaurant.tables.filter(
            assigned_waiter_staff=None, 
            assigned_waiter=None,  # Mantener compatibilidad temporal
            is_active=True
        )
        
        # Calcular promedios
        orders_today_count = orders_today.count()
        orders_month_count = orders_month.count()
        
        avg_order_today = sales_today / orders_today_count if orders_today_count > 0 else 0
        avg_order_month = sales_month / orders_month_count if orders_month_count > 0 else 0
        
        context.update({
            'page_title': 'Dashboard Administrativo',
            
            # Estadísticas de órdenes
            'orders_today_count': orders_today_count,
            'orders_week_count': orders_week.count(),
            'orders_month_count': orders_month_count,
            
            # Estadísticas de ventas
            'sales_today': sales_today,
            'sales_week': sales_week,
            'sales_month': sales_month,
            
            # Promedios
            'avg_order_today': avg_order_today,
            'avg_order_month': avg_order_month,
            
            # Datos para el dashboard
            'pending_orders': pending_orders,
            'top_products': top_products,
            'active_waiters_count': active_waiter_staff.count(),  # Ahora usa WaiterStaff
            'total_active_staff': total_active_staff,
            'staff_breakdown': {
                'waiters': active_waiter_staff.count(),  # Ahora usa WaiterStaff
                'kitchen_staff': active_kitchen_staff.count(),
                'bar_staff': active_bar_staff.count(),
                'waiter_staff': active_waiter_staff.count(),
            },
            'total_tables': restaurant.tables.count(),
            'tables_without_waiter': tables_without_waiter,
            
            # Alertas
            'alerts': {
                'tables_without_waiter': tables_without_waiter.count(),
                'inactive_waiters': WaiterStaff.objects.filter(restaurant=restaurant, status='inactive').count(),
                'inactive_kitchen_staff': KitchenStaff.objects.filter(restaurant=restaurant, status='inactive').count(),
                'inactive_bar_staff': BarStaff.objects.filter(restaurant=restaurant, status='inactive').count(),
                'staff_without_shifts': (
                    KitchenStaff.objects.filter(restaurant=restaurant, shift_start__isnull=True).count() +
                    BarStaff.objects.filter(restaurant=restaurant, shift_start__isnull=True).count() +
                    WaiterStaff.objects.filter(restaurant=restaurant, shift_start__isnull=True).count()
                ),
            },
            
            # Configuración de QR
            'qr_config': current_qr_config,
        })
        
        return context
    
    def _get_qr_detection_method(self, table):
        """Determinar qué método se está usando para generar URLs de QR"""
        if not table:
            return "No hay mesas configuradas"
        
        if hasattr(self.request, 'build_absolute_uri'):
            return "🏆 Detección automática desde request"
        elif self.request.restaurant.tenant.domain:
            return f"🏢 Dominio personalizado: {self.request.restaurant.tenant.domain}"
        else:
            from django.conf import settings
            if getattr(settings, 'QR_BASE_URL', None):
                return f"⚙️ Configuración en settings: {settings.QR_BASE_URL}"
            else:
                return "🔄 Fallback automático"


# ============================================================================
# GESTIÓN DE MENÚ
# ============================================================================

class MenuManagementView(RestaurantAdminMixin, ListView):
    """Vista para gestión del menú"""
    model = MenuItem
    template_name = 'restaurants/admin/menu/list.html'
    context_object_name = 'menu_items'
    paginate_by = 20
    
    def get_queryset(self):
        restaurant = self.request.restaurant
        queryset = MenuItem.objects.filter(tenant=restaurant.tenant).select_related('category')
        
        # Filtros
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        
        is_available = self.request.GET.get('available')
        if is_available == 'true':
            queryset = queryset.filter(is_available=True)
        elif is_available == 'false':
            queryset = queryset.filter(is_available=False)
        
        return queryset.order_by('category__name', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.request.restaurant
        
        context.update({
            'page_title': 'Gestión del Menú',
            'categories': MenuCategory.objects.filter(tenant=restaurant.tenant),
            'current_category': self.request.GET.get('category'),
            'search_query': self.request.GET.get('search', ''),
            'available_filter': self.request.GET.get('available', ''),
        })
        
        return context


@restaurant_admin_required
def create_menu_item(request, tenant_slug):
    """Crear nuevo item del menú"""
    restaurant = request.restaurant
    
    if request.method == 'POST':
        try:
            # Crear item del menú
            item = MenuItem.objects.create(
                tenant=restaurant.tenant,
                category_id=request.POST.get('category'),
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                base_price=request.POST.get('base_price'),
                preparation_time=request.POST.get('preparation_time') or None,
                is_available=request.POST.get('is_available') == 'on'
            )
            
            # Manejar la imagen si se subió
            if request.FILES.get('image'):
                item.image = request.FILES['image']
                item.save()
            
            messages.success(request, f'Producto "{item.name}" creado exitosamente.')
            return redirect('restaurants:admin_menu', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al crear el producto: {e}')
    
    categories = MenuCategory.objects.filter(tenant=restaurant.tenant)
    
    context = {
        'restaurant': restaurant,
        'categories': categories,
        'page_title': 'Crear Producto',
        'is_admin_dashboard': True,
    }
    
    return render(request, 'restaurants/admin/menu/form.html', context)


@restaurant_admin_required
def edit_menu_item(request, tenant_slug, item_id):
    """Editar item del menú"""
    restaurant = request.restaurant
    item = get_object_or_404(MenuItem, id=item_id, tenant=restaurant.tenant)
    
    if request.method == 'POST':
        try:
            item.category_id = request.POST.get('category')
            item.name = request.POST.get('name')
            item.description = request.POST.get('description', '')
            item.base_price = request.POST.get('base_price')
            item.preparation_time = request.POST.get('preparation_time') or None
            item.is_available = request.POST.get('is_available') == 'on'
            
            # Manejar la imagen si se subió
            if request.FILES.get('image'):
                item.image = request.FILES['image']
            
            item.save()
            
            messages.success(request, f'Producto "{item.name}" actualizado exitosamente.')
            return redirect('restaurants:admin_menu', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el producto: {e}')
    
    categories = MenuCategory.objects.filter(tenant=restaurant.tenant)
    
    context = {
        'restaurant': restaurant,
        'item': item,
        'categories': categories,
        'page_title': f'Editar {item.name}',
        'is_admin_dashboard': True,
    }
    
    return render(request, 'restaurants/admin/menu/form.html', context)


@restaurant_admin_required
@require_POST
def delete_menu_item(request, tenant_slug, item_id):
    """Eliminar item del menú (AJAX)"""
    try:
        restaurant = request.restaurant
        item = get_object_or_404(MenuItem, id=item_id, tenant=restaurant.tenant)
        item_name = item.name
        item.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Producto "{item_name}" eliminado exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ============================================================================
# GESTIÓN DE MESAS
# ============================================================================

class TablesManagementView(RestaurantAdminMixin, ListView):
    """Vista para gestión de mesas"""
    model = Table
    template_name = 'restaurants/admin/tables/list.html'
    context_object_name = 'tables'
    
    def get_queryset(self):
        return Table.objects.filter(
            restaurant=self.request.restaurant
        ).select_related('assigned_waiter_staff__user').order_by('number')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.request.restaurant
        
        # Sistema de meseros unificado (solo WaiterStaff)
        waiter_staff = WaiterStaff.objects.filter(restaurant=restaurant, status='active')
        
        context.update({
            'page_title': 'Gestión de Mesas',
            'waiter_staff': waiter_staff,
        })
        
        return context


@restaurant_admin_required
def create_table_admin(request, tenant_slug):
    """Crear nueva mesa"""
    restaurant = request.restaurant
    
    if request.method == 'POST':
        try:
            # Solo usar WaiterStaff para asignación
            assigned_waiter_staff_id = request.POST.get('assigned_waiter_staff') or None
            
            table = Table.objects.create(
                restaurant=restaurant,
                number=request.POST.get('number'),
                name=request.POST.get('name', ''),
                capacity=request.POST.get('capacity', 4),
                location=request.POST.get('location', ''),
                assigned_waiter_staff_id=assigned_waiter_staff_id,
            )
            
            messages.success(request, f'Mesa {table.number} creada exitosamente.')
            return redirect('restaurants:admin_tables', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al crear la mesa: {e}')
    
    # Sistema de meseros unificado (solo WaiterStaff)
    waiter_staff = WaiterStaff.objects.filter(restaurant=restaurant, status='active')
    
    context = {
        'restaurant': restaurant,
        'waiter_staff': waiter_staff,
        'page_title': 'Crear Mesa',
        'is_admin_dashboard': True,
    }
    
    return render(request, 'restaurants/admin/tables/form.html', context)


@restaurant_admin_required
def edit_table_admin(request, tenant_slug, table_id):
    """Editar mesa"""
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    
    if request.method == 'POST':
        try:
            # Solo usar WaiterStaff para asignación
            assigned_waiter_staff_id = request.POST.get('assigned_waiter_staff') or None
            
            table.number = request.POST.get('number')
            table.name = request.POST.get('name', '')
            table.capacity = request.POST.get('capacity')
            table.location = request.POST.get('location', '')
            table.assigned_waiter_staff_id = assigned_waiter_staff_id
            table.is_active = request.POST.get('is_active') == 'on'
            table.qr_enabled = request.POST.get('qr_enabled') == 'on'
            table.save()
            
            messages.success(request, f'Mesa {table.number} actualizada exitosamente.')
            return redirect('restaurants:admin_tables', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar la mesa: {e}')
    
    # Sistema de meseros unificado (solo WaiterStaff)
    waiter_staff = WaiterStaff.objects.filter(restaurant=restaurant, status='active')
    
    context = {
        'restaurant': restaurant,
        'table': table,
        'waiter_staff': waiter_staff,
        'page_title': f'Editar Mesa {table.number}',
        'is_admin_dashboard': True,
    }
    
    return render(request, 'restaurants/admin/tables/form.html', context)


@restaurant_admin_required
@require_POST
def delete_table(request, tenant_slug, table_id):
    """Eliminar mesa (AJAX)"""
    try:
        restaurant = request.restaurant
        table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
        
        table_number = table.number
        table.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Mesa {table_number} eliminada exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@restaurant_admin_required
def table_qr_preview(request, tenant_slug, table_id):
    """Vista previa del QR de la mesa con URL visible"""
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    
    # Generar QR con URL dinámica
    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr_url = table.get_full_qr_url(request)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a base64 para mostrar en template
    import io
    import base64
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    context = {
        'restaurant': restaurant,
        'table': table,
        'qr_url': qr_url,
        'qr_image_base64': img_base64,
        'page_title': f'QR Mesa {table.number}',
        'is_admin_dashboard': True,
    }
    
    return render(request, 'restaurants/admin/tables/qr_preview.html', context)


@restaurant_admin_required
def table_qr_download(request, tenant_slug, table_id):
    """Descargar QR de la mesa"""
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    
    # Generar QR con URL dinámica
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr_url = table.get_full_qr_url(request)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Crear response
    response = HttpResponse(content_type="image/png")
    response['Content-Disposition'] = f'attachment; filename="mesa_{table.number}_qr.png"'
    img.save(response, "PNG")
    
    return response


# ============================================================================
# REPORTES Y ANALYTICS
# ============================================================================

class SalesReportView(RestaurantAdminMixin, TemplateView):
    """Vista de reportes de ventas"""
    template_name = 'restaurants/admin/reports/sales.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.request.restaurant
        
        # Filtros de fecha
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if not date_from:
            date_from = (timezone.now() - timedelta(days=30)).date()
        else:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        
        if not date_to:
            date_to = timezone.now().date()
        else:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        # Filtrar órdenes
        orders = Order.objects.filter(
            restaurant=restaurant,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
            status__in=['delivered', 'ready']
        )
        
        # Estadísticas generales
        total_orders = orders.count()
        total_revenue = orders.aggregate(total=Sum('total_amount'))['total'] or 0
        average_order = total_revenue / total_orders if total_orders > 0 else 0
        
        # Ventas por día
        daily_sales = orders.extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount')
        ).order_by('date')
        
        # Productos más vendidos
        top_products = OrderItem.objects.filter(
            order__in=orders
        ).values(
            'menu_item__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_revenue')[:10]
        
        context.update({
            'page_title': 'Reportes de Ventas',
            'date_from': date_from,
            'date_to': date_to,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'average_order': average_order,
            'daily_sales': daily_sales,
            'top_products': top_products,
        })
        
        return context 


# ============================================================================
# GESTIÓN DE PERSONAL DE COCINA
# ============================================================================

class KitchenStaffManagementView(RestaurantAdminMixin, ListView):
    """Vista para gestión de personal de cocina"""
    model = KitchenStaff
    template_name = 'restaurants/admin/kitchen_staff/list.html'
    context_object_name = 'kitchen_staff'
    
    def get_queryset(self):
        return KitchenStaff.objects.filter(
            restaurant=self.request.restaurant
        ).select_related('user')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Gestión de Personal de Cocina'
        return context


@restaurant_admin_required
def create_kitchen_staff(request, tenant_slug):
    """Crear personal de cocina"""
    restaurant = request.restaurant
    
    if request.method == 'POST':
        try:
            # Crear usuario
            user = User.objects.create_user(
                username=request.POST.get('username'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                email=request.POST.get('email'),
                password=request.POST.get('password')
            )
            
            # Generar ID automáticamente si no se proporciona
            employee_id = request.POST.get('employee_id', '').strip()
            if not employee_id:
                employee_id = KitchenStaff.generate_employee_id(restaurant)
            
            # Crear personal de cocina
            kitchen_staff = KitchenStaff.objects.create(
                user=user,
                restaurant=restaurant,
                employee_id=employee_id,
                phone=request.POST.get('phone', ''),
                status=request.POST.get('status'),
                shift_start=request.POST.get('shift_start') or None,
                shift_end=request.POST.get('shift_end') or None,
                priority_level=request.POST.get('priority_level', 'medium'),
                years_experience=request.POST.get('years_experience', 0)
            )
            
            # Agregar especialidades si se proporcionaron
            specialties = request.POST.getlist('specialties')
            kitchen_staff.specialties = specialties
            kitchen_staff.save()
            
            messages.success(request, f'Personal de cocina "{kitchen_staff.full_name}" creado exitosamente.')
            return redirect('restaurants:admin_kitchen_staff', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al crear el personal de cocina: {e}')
    
    # Especialidades predefinidas para cocina
    KITCHEN_SPECIALTIES = [
        {'id': 'pasta', 'name': 'Pasta y Fideos'},
        {'id': 'pizza', 'name': 'Pizza'},
        {'id': 'carnes', 'name': 'Carnes y Parrilla'},
        {'id': 'pescados', 'name': 'Pescados y Mariscos'},
        {'id': 'ensaladas', 'name': 'Ensaladas'},
        {'id': 'sopas', 'name': 'Sopas y Cremas'},
        {'id': 'postres', 'name': 'Postres'},
        {'id': 'comida_rapida', 'name': 'Comida Rápida'},
        {'id': 'reposteria', 'name': 'Repostería'},
        {'id': 'cocina_internacional', 'name': 'Cocina Internacional'},
    ]
    
    context = {
        'restaurant': restaurant,
        'page_title': 'Crear Personal de Cocina',
        'is_admin_dashboard': True,
        'status_choices': KitchenStaff.STATUS_CHOICES,
        'priority_choices': KitchenStaff.PRIORITY_CHOICES,
        'specialties': KITCHEN_SPECIALTIES,
        'suggested_employee_id': KitchenStaff.generate_employee_id(restaurant),
    }
    
    return render(request, 'restaurants/admin/kitchen_staff/form.html', context)


@restaurant_admin_required
def edit_kitchen_staff(request, tenant_slug, staff_id):
    """Editar personal de cocina"""
    restaurant = request.restaurant
    kitchen_staff = get_object_or_404(KitchenStaff, id=staff_id, restaurant=restaurant)
    
    if request.method == 'POST':
        try:
            # Actualizar usuario
            user = kitchen_staff.user
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            
            if request.POST.get('password'):
                user.set_password(request.POST.get('password'))
            
            user.save()
            
            # Actualizar personal de cocina
            kitchen_staff.employee_id = request.POST.get('employee_id', '')
            kitchen_staff.phone = request.POST.get('phone', '')
            kitchen_staff.status = request.POST.get('status')
            kitchen_staff.shift_start = request.POST.get('shift_start') or None
            kitchen_staff.shift_end = request.POST.get('shift_end') or None
            kitchen_staff.priority_level = request.POST.get('priority_level', 'medium')
            kitchen_staff.years_experience = request.POST.get('years_experience', 0)
            kitchen_staff.save()
            
            # Actualizar especialidades
            specialties = request.POST.getlist('specialties')
            kitchen_staff.specialties = specialties
            
            messages.success(request, f'Personal de cocina "{kitchen_staff.full_name}" actualizado exitosamente.')
            return redirect('restaurants:admin_kitchen_staff', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el personal de cocina: {e}')
    
    # Especialidades predefinidas para cocina (mismas que en create)
    KITCHEN_SPECIALTIES = [
        {'id': 'pasta', 'name': 'Pasta y Fideos'},
        {'id': 'pizza', 'name': 'Pizza'},
        {'id': 'carnes', 'name': 'Carnes y Parrilla'},
        {'id': 'pescados', 'name': 'Pescados y Mariscos'},
        {'id': 'ensaladas', 'name': 'Ensaladas'},
        {'id': 'sopas', 'name': 'Sopas y Cremas'},
        {'id': 'postres', 'name': 'Postres'},
        {'id': 'comida_rapida', 'name': 'Comida Rápida'},
        {'id': 'reposteria', 'name': 'Repostería'},
        {'id': 'cocina_internacional', 'name': 'Cocina Internacional'},
    ]
    
    context = {
        'restaurant': restaurant,
        'kitchen_staff': kitchen_staff,
        'page_title': f'Editar {kitchen_staff.full_name}',
        'is_admin_dashboard': True,
        'status_choices': KitchenStaff.STATUS_CHOICES,
        'priority_choices': KitchenStaff.PRIORITY_CHOICES,
        'specialties': KITCHEN_SPECIALTIES,
    }
    
    return render(request, 'restaurants/admin/kitchen_staff/form.html', context)


@restaurant_admin_required
@require_POST
def delete_kitchen_staff(request, tenant_slug, staff_id):
    """Eliminar personal de cocina"""
    restaurant = request.restaurant
    kitchen_staff = get_object_or_404(KitchenStaff, id=staff_id, restaurant=restaurant)
    
    try:
        staff_name = kitchen_staff.full_name
        user = kitchen_staff.user
        kitchen_staff.delete()
        user.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Personal de cocina "{staff_name}" eliminado exitosamente.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ============================================================================
# GESTIÓN DE PERSONAL DE BAR
# ============================================================================

class BarStaffManagementView(RestaurantAdminMixin, ListView):
    """Vista para gestión de personal de bar"""
    model = BarStaff
    template_name = 'restaurants/admin/bar_staff/list.html'
    context_object_name = 'bar_staff'
    
    def get_queryset(self):
        return BarStaff.objects.filter(
            restaurant=self.request.restaurant
        ).select_related('user')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Gestión de Personal de Bar'
        return context


@restaurant_admin_required
def create_bar_staff(request, tenant_slug):
    """Crear personal de bar"""
    restaurant = request.restaurant
    
    if request.method == 'POST':
        try:
            # Crear usuario
            user = User.objects.create_user(
                username=request.POST.get('username'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                email=request.POST.get('email'),
                password=request.POST.get('password')
            )
            
            # Generar ID automáticamente si no se proporciona
            employee_id = request.POST.get('employee_id', '').strip()
            if not employee_id:
                employee_id = BarStaff.generate_employee_id(restaurant)
            
            # Crear personal de bar
            bar_staff = BarStaff.objects.create(
                user=user,
                restaurant=restaurant,
                employee_id=employee_id,
                phone=request.POST.get('phone', ''),
                status=request.POST.get('status'),
                shift_start=request.POST.get('shift_start') or None,
                shift_end=request.POST.get('shift_end') or None,
                can_serve_alcohol=request.POST.get('can_serve_alcohol') == 'on',
                years_experience=request.POST.get('years_experience', 0)
            )
            
            # Agregar certificaciones si se proporcionaron
            certifications = request.POST.getlist('certifications')
            bar_staff.certifications = certifications
            bar_staff.save()
            
            messages.success(request, f'Personal de bar "{bar_staff.full_name}" creado exitosamente.')
            return redirect('restaurants:admin_bar_staff', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al crear el personal de bar: {e}')
    
    # Certificaciones predefinidas para bar
    BAR_CERTIFICATIONS = [
        {'id': 'bartender', 'name': 'Certificación de Bartender'},
        {'id': 'sommelier', 'name': 'Sommelier'},
        {'id': 'barista', 'name': 'Barista Profesional'},
        {'id': 'mixologia', 'name': 'Mixología Avanzada'},
        {'id': 'responsable_consumo', 'name': 'Servicio Responsable de Alcohol'},
        {'id': 'higiene_alimentos', 'name': 'Manipulación de Alimentos'},
        {'id': 'primeros_auxilios', 'name': 'Primeros Auxilios'},
    ]
    
    context = {
        'restaurant': restaurant,
        'page_title': 'Crear Personal de Bar',
        'is_admin_dashboard': True,
        'status_choices': BarStaff.STATUS_CHOICES,
        'certifications': BAR_CERTIFICATIONS,
        'suggested_employee_id': BarStaff.generate_employee_id(restaurant),
    }
    
    return render(request, 'restaurants/admin/bar_staff/form.html', context)


@restaurant_admin_required
def edit_bar_staff(request, tenant_slug, staff_id):
    """Editar personal de bar"""
    restaurant = request.restaurant
    bar_staff = get_object_or_404(BarStaff, id=staff_id, restaurant=restaurant)
    
    if request.method == 'POST':
        try:
            # Actualizar usuario
            user = bar_staff.user
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            
            if request.POST.get('password'):
                user.set_password(request.POST.get('password'))
            
            user.save()
            
            # Actualizar personal de bar
            bar_staff.employee_id = request.POST.get('employee_id', '')
            bar_staff.phone = request.POST.get('phone', '')
            bar_staff.status = request.POST.get('status')
            bar_staff.shift_start = request.POST.get('shift_start') or None
            bar_staff.shift_end = request.POST.get('shift_end') or None
            bar_staff.can_serve_alcohol = request.POST.get('can_serve_alcohol') == 'on'
            bar_staff.years_experience = request.POST.get('years_experience', 0)
            bar_staff.save()
            
            # Actualizar certificaciones
            certifications = request.POST.getlist('certifications')
            bar_staff.certifications = certifications
            
            messages.success(request, f'Personal de bar "{bar_staff.full_name}" actualizado exitosamente.')
            return redirect('restaurants:admin_bar_staff', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el personal de bar: {e}')
    
    # Certificaciones predefinidas para bar (mismas que en create)
    BAR_CERTIFICATIONS = [
        {'id': 'bartender', 'name': 'Certificación de Bartender'},
        {'id': 'sommelier', 'name': 'Sommelier'},
        {'id': 'barista', 'name': 'Barista Profesional'},
        {'id': 'mixologia', 'name': 'Mixología Avanzada'},
        {'id': 'responsable_consumo', 'name': 'Servicio Responsable de Alcohol'},
        {'id': 'higiene_alimentos', 'name': 'Manipulación de Alimentos'},
        {'id': 'primeros_auxilios', 'name': 'Primeros Auxilios'},
    ]
    
    context = {
        'restaurant': restaurant,
        'bar_staff': bar_staff,
        'page_title': f'Editar {bar_staff.full_name}',
        'is_admin_dashboard': True,
        'status_choices': BarStaff.STATUS_CHOICES,
        'certifications': BAR_CERTIFICATIONS,
    }
    
    return render(request, 'restaurants/admin/bar_staff/form.html', context)


@restaurant_admin_required
@require_POST
def delete_bar_staff(request, tenant_slug, staff_id):
    """Eliminar personal de bar"""
    restaurant = request.restaurant
    bar_staff = get_object_or_404(BarStaff, id=staff_id, restaurant=restaurant)
    
    try:
        staff_name = bar_staff.full_name
        user = bar_staff.user
        bar_staff.delete()
        user.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Personal de bar "{staff_name}" eliminado exitosamente.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ============================================================================
# GESTIÓN DE PERSONAL DE MESEROS (NUEVO MODELO)
# ============================================================================

class WaiterStaffManagementView(RestaurantAdminMixin, ListView):
    """Vista para gestión de personal de meseros (nuevo modelo)"""
    model = WaiterStaff
    template_name = 'restaurants/admin/waiter_staff/list.html'
    context_object_name = 'waiter_staff'
    
    def get_queryset(self):
        return WaiterStaff.objects.filter(
            restaurant=self.request.restaurant
        ).select_related('user')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Gestión de Meseros'
        return context


@restaurant_admin_required
def create_waiter_staff(request, tenant_slug):
    """Crear mesero (nuevo sistema)"""
    restaurant = request.restaurant
    
    if request.method == 'POST':
        try:
            # Crear usuario
            user = User.objects.create_user(
                username=request.POST.get('username'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                email=request.POST.get('email'),
                password=request.POST.get('password')
            )
            
            # Generar ID automáticamente si no se proporciona
            employee_id = request.POST.get('employee_id', '').strip()
            if not employee_id:
                employee_id = WaiterStaff.generate_employee_id(restaurant)
            
            # Crear mesero
            waiter_staff = WaiterStaff.objects.create(
                user=user,
                restaurant=restaurant,
                employee_id=employee_id,
                phone=request.POST.get('phone', ''),
                status=request.POST.get('status'),
                shift_start=request.POST.get('shift_start') or None,
                shift_end=request.POST.get('shift_end') or None,
                years_experience=request.POST.get('years_experience', 0),
                tips_percentage=request.POST.get('tips_percentage') or None,
                max_tables_assigned=request.POST.get('max_tables', 6)
            )
            
            messages.success(request, f'Mesero "{waiter_staff.full_name}" creado exitosamente.')
            return redirect('restaurants:admin_waiter_staff', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al crear el mesero: {e}')
    
    context = {
        'restaurant': restaurant,
        'page_title': 'Crear Mesero',
        'is_admin_dashboard': True,
        'status_choices': WaiterStaff.STATUS_CHOICES,
        'suggested_employee_id': WaiterStaff.generate_employee_id(restaurant),
    }
    
    return render(request, 'restaurants/admin/waiter_staff/form.html', context)


@restaurant_admin_required
def edit_waiter_staff(request, tenant_slug, staff_id):
    """Editar mesero (nuevo sistema)"""
    restaurant = request.restaurant
    waiter_staff = get_object_or_404(WaiterStaff, id=staff_id, restaurant=restaurant)
    
    if request.method == 'POST':
        try:
            # Actualizar usuario
            user = waiter_staff.user
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            
            if request.POST.get('password'):
                user.set_password(request.POST.get('password'))
            
            user.save()
            
            # Actualizar mesero
            waiter_staff.employee_id = request.POST.get('employee_id', '')
            waiter_staff.phone = request.POST.get('phone', '')
            waiter_staff.status = request.POST.get('status')
            waiter_staff.shift_start = request.POST.get('shift_start') or None
            waiter_staff.shift_end = request.POST.get('shift_end') or None
            waiter_staff.years_experience = request.POST.get('years_experience', 0)
            waiter_staff.tips_percentage = request.POST.get('tips_percentage') or None
            waiter_staff.max_tables_assigned = request.POST.get('max_tables', 6)
            waiter_staff.save()
            
            messages.success(request, f'Mesero "{waiter_staff.full_name}" actualizado exitosamente.')
            return redirect('restaurants:admin_waiter_staff', tenant_slug=tenant_slug)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el mesero: {e}')
    
    context = {
        'restaurant': restaurant,
        'waiter_staff': waiter_staff,
        'page_title': f'Editar {waiter_staff.full_name}',
        'is_admin_dashboard': True,
        'status_choices': WaiterStaff.STATUS_CHOICES,
    }
    
    return render(request, 'restaurants/admin/waiter_staff/form.html', context)


@restaurant_admin_required
@require_POST
def delete_waiter_staff(request, tenant_slug, staff_id):
    """Eliminar mesero (nuevo sistema)"""
    restaurant = request.restaurant
    waiter_staff = get_object_or_404(WaiterStaff, id=staff_id, restaurant=restaurant)
    
    try:
        staff_name = waiter_staff.full_name
        user = waiter_staff.user
        waiter_staff.delete()
        user.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Mesero "{staff_name}" eliminado exitosamente.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }) 