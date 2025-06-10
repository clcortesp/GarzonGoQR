"""
Vistas específicas para el personal de cocina
Gestiona solo items de tipo 'food' en los pedidos
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count

from .models import KitchenStaff
from .staff_middleware import staff_required_by_role
from orders.models import Order, OrderItem


@login_required
@staff_required_by_role('kitchen')
def kitchen_dashboard(request, tenant_slug):
    """
    Dashboard principal para personal de cocina
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member  # Del middleware
        
        if not isinstance(staff_member, KitchenStaff):
            messages.error(request, 'No tienes permisos de cocina para este restaurante.')
            return redirect('/')
        
        # Obtener pedidos con items de comida
        kitchen_orders = get_kitchen_orders(restaurant)
        
        # Estadísticas del día
        today = timezone.now().date()
        today_stats = get_kitchen_stats(restaurant, today)
        
        # Items pendientes de preparar
        pending_items = get_pending_food_items(restaurant)
        
        # Items en preparación
        preparing_items = get_preparing_food_items(restaurant, staff_member)
        
        context = {
            'restaurant': restaurant,
            'tenant': restaurant.tenant,
            'staff_member': staff_member,
            'staff_context': getattr(request, 'staff_context', {}),
            
            # Órdenes y items
            'kitchen_orders': kitchen_orders[:10],  # Últimas 10
            'pending_items': pending_items,
            'preparing_items': preparing_items,
            
            # Estadísticas
            'pending_items_count': len(pending_items),
            'preparing_items_count': len(preparing_items),
            'today_orders_count': today_stats['orders_count'],
            'today_items_prepared': today_stats['items_prepared'],
            'avg_prep_time': staff_member.average_prep_time,
            
            # Estado
            'is_available': staff_member.is_available,
            'is_working_hours': staff_member.is_working_hours,
            'can_modify_prep_time': staff_member.can_modify_prep_time,
            
            # Configuración
            'role': 'kitchen',
            'page_title': 'Dashboard Cocina',
        }
        
        return render(request, 'restaurants/kitchen_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando dashboard de cocina: {e}')
        return redirect('/')


@login_required
@staff_required_by_role('kitchen')
def kitchen_orders_list(request, tenant_slug):
    """
    Lista completa de pedidos para cocina con filtros
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member
        
        # Filtros
        status_filter = request.GET.get('status', 'pending')
        order_type = request.GET.get('type', 'all')
        date_filter = request.GET.get('date', 'today')
        
        # Base query: solo items de comida
        food_items = OrderItem.objects.filter(
            order__table__restaurant=restaurant,
            menu_item__item_type__in=['food', 'both']
        ).select_related('order', 'menu_item', 'order__table')
        
        # Aplicar filtros
        if status_filter != 'all':
            food_items = food_items.filter(status=status_filter)
        
        if order_type != 'all':
            food_items = food_items.filter(order__order_type=order_type)
        
        # Filtro de fecha
        if date_filter == 'today':
            today = timezone.now().date()
            food_items = food_items.filter(order__created_at__date=today)
        elif date_filter == 'week':
            week_start = timezone.now().date() - timezone.timedelta(days=7)
            food_items = food_items.filter(order__created_at__date__gte=week_start)
        
        # Ordenar por prioridad: pending primero, luego por hora
        food_items = food_items.order_by(
            'status',  # pending viene antes
            'order__created_at'
        )
        
        # Paginación
        paginator = Paginator(food_items, 20)
        page_obj = paginator.get_page(request.GET.get('page'))
        
        context = {
            'restaurant': restaurant,
            'staff_member': staff_member,
            'page_obj': page_obj,
            'status_filter': status_filter,
            'order_type': order_type,
            'date_filter': date_filter,
            'role': 'kitchen',
            'page_title': 'Pedidos de Cocina',
        }
        
        return render(request, 'restaurants/kitchen_orders_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando pedidos: {e}')
        return redirect('restaurants:kitchen_dashboard', tenant_slug=tenant_slug)


@login_required
@staff_required_by_role('kitchen')
@require_POST
def update_item_status(request, tenant_slug, item_id):
    """
    Actualizar estado de un item de comida (AJAX)
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member
        
        # Obtener item y verificar que sea de comida
        item = get_object_or_404(
            OrderItem, 
            id=item_id,
            order__table__restaurant=restaurant,
            menu_item__item_type__in=['food', 'both']
        )
        
        new_status = request.POST.get('status')
        
        if new_status not in ['pending', 'preparing', 'ready']:
            return JsonResponse({
                'success': False,
                'error': 'Estado inválido'
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
            # Actualizar estadísticas del cocinero
            staff_member.total_dishes_prepared += 1
            staff_member.save()
        
        item.save()
        
        # TODO: Enviar notificación al garzón si el item está listo
        if new_status == 'ready':
            # Aquí integrarías con el sistema de notificaciones
            pass
        
        return JsonResponse({
            'success': True,
            'message': f'Item actualizado a {item.get_status_display()}',
            'new_status': new_status,
            'status_display': item.get_status_display()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@staff_required_by_role('kitchen')
@require_POST
def update_prep_time(request, tenant_slug, item_id):
    """
    Actualizar tiempo estimado de preparación (solo si tiene permisos)
    """
    try:
        restaurant = request.restaurant
        staff_member = request.staff_member
        
        if not staff_member.can_modify_prep_time:
            return JsonResponse({
                'success': False,
                'error': 'No tienes permisos para modificar tiempos'
            })
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id,
            order__table__restaurant=restaurant,
            menu_item__item_type__in=['food', 'both']
        )
        
        new_prep_time = request.POST.get('prep_time')
        
        try:
            new_prep_time = int(new_prep_time)
            if new_prep_time < 1 or new_prep_time > 180:  # 1-180 minutos
                raise ValueError()
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Tiempo inválido (1-180 minutos)'
            })
        
        # Actualizar tiempo estimado
        item.estimated_prep_time = new_prep_time
        item.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Tiempo actualizado a {new_prep_time} minutos'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@staff_required_by_role('kitchen')
@require_POST
def update_kitchen_status(request, tenant_slug):
    """
    Actualizar estado de disponibilidad del cocinero
    """
    try:
        staff_member = request.staff_member
        
        new_status = request.POST.get('status')
        is_available = request.POST.get('is_available') == 'true'
        
        if new_status and new_status in dict(KitchenStaff.STATUS_CHOICES):
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


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_kitchen_orders(restaurant):
    """
    Obtener pedidos que contienen items de comida
    """
    return Order.objects.filter(
        table__restaurant=restaurant,
        order_items__menu_item__item_type__in=['food', 'both']
    ).distinct().select_related('table').order_by('-created_at')


def get_pending_food_items(restaurant):
    """
    Obtener items de comida pendientes de preparar
    """
    return OrderItem.objects.filter(
        order__table__restaurant=restaurant,
        menu_item__item_type__in=['food', 'both'],
        status='pending'
    ).select_related('order', 'menu_item', 'order__table').order_by('order__created_at')


def get_preparing_food_items(restaurant, staff_member):
    """
    Obtener items en preparación (opcionalmente filtrados por cocinero)
    """
    items = OrderItem.objects.filter(
        order__table__restaurant=restaurant,
        menu_item__item_type__in=['food', 'both'],
        status='preparing'
    ).select_related('order', 'menu_item', 'order__table')
    
    # Si tienes campo prepared_by, filtrar por el cocinero actual
    # items = items.filter(prepared_by=staff_member.user)
    
    return items.order_by('started_at')


def get_kitchen_stats(restaurant, date):
    """
    Obtener estadísticas de cocina para una fecha
    """
    food_items = OrderItem.objects.filter(
        order__table__restaurant=restaurant,
        menu_item__item_type__in=['food', 'both'],
        order__created_at__date=date
    )
    
    return {
        'orders_count': Order.objects.filter(
            table__restaurant=restaurant,
            created_at__date=date,
            order_items__menu_item__item_type__in=['food', 'both']
        ).distinct().count(),
        'items_prepared': food_items.filter(status='ready').count(),
        'items_pending': food_items.filter(status='pending').count(),
        'items_preparing': food_items.filter(status='preparing').count(),
    } 