"""
Vistas específicas para el personal de bar
Gestiona solo items de tipo 'drink' en los pedidos
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count

from .models import BarStaff
from .staff_middleware import staff_required_by_role
from orders.models import Order, OrderItem


@login_required
@staff_required_by_role('bar')
def bar_dashboard(request, tenant_slug):
    """
    Dashboard principal para personal de bar
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member  # Del middleware
        
        if not isinstance(staff_member, BarStaff):
            messages.error(request, 'No tienes permisos de bar para este restaurante.')
            return redirect('/')
        
        # Obtener pedidos con items de bebida
        bar_orders = get_bar_orders(restaurant)
        
        # Estadísticas del día
        today = timezone.now().date()
        today_stats = get_bar_stats(restaurant, today)
        
        # Items pendientes de preparar
        pending_drinks = get_pending_drink_items(restaurant)
        
        # Items en preparación
        preparing_drinks = get_preparing_drink_items(restaurant, staff_member)
        
        # Bebidas más pedidas del día
        popular_drinks = get_popular_drinks_today(restaurant)
        
        context = {
            'restaurant': restaurant,
            'tenant': restaurant.tenant,
            'staff_member': staff_member,
            'staff_context': getattr(request, 'staff_context', {}),
            
            # Órdenes y items
            'bar_orders': bar_orders[:10],  # Últimas 10
            'pending_drinks': pending_drinks,
            'preparing_drinks': preparing_drinks,
            'popular_drinks': popular_drinks,
            
            # Estadísticas
            'pending_drinks_count': len(pending_drinks),
            'preparing_drinks_count': len(preparing_drinks),
            'today_orders_count': today_stats['orders_count'],
            'today_drinks_prepared': today_stats['drinks_prepared'],
            'avg_prep_time': staff_member.average_prep_time,
            
            # Estado y permisos
            'is_available': staff_member.is_available,
            'is_working_hours': staff_member.is_working_hours,
            'can_serve_alcohol': staff_member.can_serve_alcohol,
            'has_bartender_license': staff_member.has_bartender_license,
            'drink_specialties': staff_member.drink_specialties,
            
            # Configuración
            'role': 'bar',
            'page_title': 'Dashboard Bar',
        }
        
        return render(request, 'restaurants/bar_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando dashboard de bar: {e}')
        return redirect('/')


@login_required
@staff_required_by_role('bar')
def bar_orders_list(request, tenant_slug):
    """
    Lista completa de pedidos de bebidas con filtros
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member
        
        # Filtros
        status_filter = request.GET.get('status', 'pending')
        drink_type = request.GET.get('drink_type', 'all')
        date_filter = request.GET.get('date', 'today')
        alcohol_filter = request.GET.get('alcohol', 'all')
        
        # Base query: solo items de bebida
        drink_items = OrderItem.objects.filter(
            order__table__restaurant=restaurant,
            menu_item__item_type__in=['drink', 'both']
        ).select_related('order', 'menu_item', 'order__table')
        
        # Aplicar filtros
        if status_filter != 'all':
            drink_items = drink_items.filter(status=status_filter)
        
        # Filtro por tipo de bebida (basado en categoría)
        if drink_type != 'all':
            drink_items = drink_items.filter(menu_item__category__name__icontains=drink_type)
        
        # Filtro de alcohol (si el barman no puede servir alcohol)
        if alcohol_filter == 'non_alcoholic' or not staff_member.can_serve_alcohol:
            # Filtrar bebidas sin alcohol (basado en categoría o tags)
            drink_items = drink_items.exclude(
                menu_item__category__name__icontains='cerveza'
            ).exclude(
                menu_item__category__name__icontains='vino'
            ).exclude(
                menu_item__category__name__icontains='cocktail'
            )
        
        # Filtro de fecha
        if date_filter == 'today':
            today = timezone.now().date()
            drink_items = drink_items.filter(order__created_at__date=today)
        elif date_filter == 'week':
            week_start = timezone.now().date() - timezone.timedelta(days=7)
            drink_items = drink_items.filter(order__created_at__date__gte=week_start)
        
        # Ordenar por prioridad: pending primero, luego por hora
        drink_items = drink_items.order_by(
            'status',  # pending viene antes
            'order__created_at'
        )
        
        # Paginación
        paginator = Paginator(drink_items, 25)
        page_obj = paginator.get_page(request.GET.get('page'))
        
        context = {
            'restaurant': restaurant,
            'staff_member': staff_member,
            'page_obj': page_obj,
            'status_filter': status_filter,
            'drink_type': drink_type,
            'date_filter': date_filter,
            'alcohol_filter': alcohol_filter,
            'role': 'bar',
            'page_title': 'Pedidos de Bar',
        }
        
        return render(request, 'restaurants/bar_orders_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando pedidos de bar: {e}')
        return redirect('restaurants:bar_dashboard', tenant_slug=tenant_slug)


@login_required
@staff_required_by_role('bar')
@require_POST
def update_drink_status(request, tenant_slug, item_id):
    """
    Actualizar estado de un item de bebida (AJAX)
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member
        
        # Obtener item y verificar que sea de bebida
        item = get_object_or_404(
            OrderItem, 
            id=item_id,
            order__table__restaurant=restaurant,
            menu_item__item_type__in=['drink', 'both']
        )
        
        new_status = request.POST.get('status')
        
        if new_status not in ['pending', 'preparing', 'ready']:
            return JsonResponse({
                'success': False,
                'error': 'Estado inválido'
            })
        
        # Verificar permisos para bebidas alcohólicas
        if not staff_member.can_serve_alcohol:
            is_alcoholic = check_if_alcoholic_drink(item.menu_item)
            if is_alcoholic:
                return JsonResponse({
                    'success': False,
                    'error': 'No tienes permisos para preparar bebidas alcohólicas'
                })
        
        # Actualizar estado
        old_status = item.status
        item.status = new_status
        
        # Agregar timestamp según el estado
        if new_status == 'preparing':
            item.started_at = timezone.now()
            item.prepared_by = staff_member.user  # Si tienes este campo
        elif new_status == 'ready':
            item.completed_at = timezone.now()
            # Actualizar estadísticas del barman
            staff_member.total_drinks_prepared += 1
            staff_member.save()
        
        item.save()
        
        # TODO: Enviar notificación al garzón si la bebida está lista
        if new_status == 'ready':
            # Aquí integrarías con el sistema de notificaciones
            pass
        
        return JsonResponse({
            'success': True,
            'message': f'Bebida actualizada a {item.get_status_display()}',
            'new_status': new_status,
            'status_display': item.get_status_display()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@staff_required_by_role('bar')
@require_POST
def update_bar_status(request, tenant_slug):
    """
    Actualizar estado de disponibilidad del barman
    """
    try:
        staff_member = request.staff_member
        
        new_status = request.POST.get('status')
        is_available = request.POST.get('is_available') == 'true'
        
        if new_status and new_status in dict(BarStaff.STATUS_CHOICES):
            staff_member.status = new_status
            staff_member.is_available = is_available
            staff_member.save()
            
            # Actualizar actividad
            staff_member.update_activity()
            
            return JsonResponse({
                'success': True,
                'message': 'Estado actualizado correctamente',
                'new_status': staff_member.get_status_display(),
                'is_available': staff_member.is_available
            })
        
        return JsonResponse({
            'success': False,
            'error': 'Estado inválido'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@staff_required_by_role('bar')
def bar_inventory_status(request, tenant_slug):
    """
    Vista para gestionar estado de inventario de bebidas (futuro)
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member
        
        # Por ahora, mostrar items de bebida disponibles
        from menu.models import MenuItem
        
        drink_items = MenuItem.objects.filter(
            tenant=restaurant.tenant,
            item_type__in=['drink', 'both'],
            is_available=True
        ).select_related('category').order_by('category__name', 'name')
        
        context = {
            'restaurant': restaurant,
            'staff_member': staff_member,
            'drink_items': drink_items,
            'role': 'bar',
            'page_title': 'Inventario de Bebidas',
        }
        
        return render(request, 'restaurants/bar_inventory.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando inventario: {e}')
        return redirect('restaurants:bar_dashboard', tenant_slug=tenant_slug)


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_bar_orders(restaurant):
    """
    Obtener pedidos que contienen items de bebida
    """
    return Order.objects.filter(
        table__restaurant=restaurant,
        order_items__menu_item__item_type__in=['drink', 'both']
    ).distinct().select_related('table').order_by('-created_at')


def get_pending_drink_items(restaurant):
    """
    Obtener items de bebida pendientes de preparar
    """
    return OrderItem.objects.filter(
        order__table__restaurant=restaurant,
        menu_item__item_type__in=['drink', 'both'],
        status='pending'
    ).select_related('order', 'menu_item', 'order__table').order_by('order__created_at')


def get_preparing_drink_items(restaurant, staff_member):
    """
    Obtener bebidas en preparación
    """
    items = OrderItem.objects.filter(
        order__table__restaurant=restaurant,
        menu_item__item_type__in=['drink', 'both'],
        status='preparing'
    ).select_related('order', 'menu_item', 'order__table')
    
    # Si tienes campo prepared_by, filtrar por el barman actual
    # items = items.filter(prepared_by=staff_member.user)
    
    return items.order_by('started_at')


def get_popular_drinks_today(restaurant):
    """
    Obtener bebidas más pedidas del día
    """
    today = timezone.now().date()
    
    popular = OrderItem.objects.filter(
        order__table__restaurant=restaurant,
        menu_item__item_type__in=['drink', 'both'],
        order__created_at__date=today
    ).values(
        'menu_item__name'
    ).annotate(
        total_ordered=Count('id')
    ).order_by('-total_ordered')[:5]
    
    return popular


def get_bar_stats(restaurant, date):
    """
    Obtener estadísticas de bar para una fecha
    """
    drink_items = OrderItem.objects.filter(
        order__table__restaurant=restaurant,
        menu_item__item_type__in=['drink', 'both'],
        order__created_at__date=date
    )
    
    return {
        'orders_count': Order.objects.filter(
            table__restaurant=restaurant,
            created_at__date=date,
            order_items__menu_item__item_type__in=['drink', 'both']
        ).distinct().count(),
        'drinks_prepared': drink_items.filter(status='ready').count(),
        'drinks_pending': drink_items.filter(status='pending').count(),
        'drinks_preparing': drink_items.filter(status='preparing').count(),
    }


def check_if_alcoholic_drink(menu_item):
    """
    Verificar si una bebida es alcohólica
    Basado en categoría o tags del item
    """
    alcoholic_keywords = [
        'cerveza', 'beer', 'vino', 'wine', 'cocktail', 'coctel', 
        'whisky', 'vodka', 'rum', 'gin', 'tequila', 'brandy',
        'licor', 'liquor', 'alcohol'
    ]
    
    # Verificar en el nombre de la categoría
    category_name = menu_item.category.name.lower()
    if any(keyword in category_name for keyword in alcoholic_keywords):
        return True
    
    # Verificar en el nombre del producto
    item_name = menu_item.name.lower()
    if any(keyword in item_name for keyword in alcoholic_keywords):
        return True
    
    # Por defecto, asumir que no es alcohólica
    return False 