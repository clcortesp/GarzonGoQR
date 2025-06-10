"""
FASE 2: Vistas especializadas para meseros con timeline granular de items
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q

from orders.models import Order, OrderItem
from .models import WaiterStaff
import logging

logger = logging.getLogger(__name__)


@login_required
def waiter_orders_timeline(request, tenant_slug):
    """
    Vista de timeline de órdenes con estado granular de items para meseros
    """
    try:
        restaurant = request.restaurant
        
        # Verificar si el usuario es mesero
        try:
            waiter_staff = WaiterStaff.objects.get(restaurant=restaurant, user=request.user)
        except WaiterStaff.DoesNotExist:
            messages.error(request, 'No tienes permisos de mesero para este restaurante.')
            return redirect('restaurants:home', tenant_slug=tenant_slug)
        
        # Obtener órdenes activas con sus items
        active_orders = Order.objects.filter(
            restaurant=restaurant,
            status__in=['confirmed', 'preparing', 'ready']
        ).select_related('table').prefetch_related(
            'items__menu_item',
            'items__selected_variant',
            'items__selected_addons',
            'items__selected_modifiers'
        ).order_by('-created_at')
        
        # Enriquecer cada orden con información granular
        orders_with_timeline = []
        for order in active_orders:
            items_by_area = {
                'kitchen': [],
                'bar': [],
            }
            
            # Separar items por área
            for item in order.items.all():
                if item.responsible_area in items_by_area:
                    items_by_area[item.responsible_area].append(item)
            
            # Calcular progreso por área
            kitchen_progress = calculate_area_progress(items_by_area['kitchen'])
            bar_progress = calculate_area_progress(items_by_area['bar'])
            
            # Estado general de la orden
            order_status = determine_order_status(order, items_by_area)
            
            orders_with_timeline.append({
                'order': order,
                'items_by_area': items_by_area,
                'kitchen_progress': kitchen_progress,
                'bar_progress': bar_progress,
                'order_status': order_status,
                'ready_for_service': can_serve_order(items_by_area),
            })
        
        # Items listos para servir
        ready_items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            status__in=['kitchen_ready', 'bar_ready', 'ready']
        ).select_related('order', 'menu_item').order_by('preparation_completed_at')
        
        context = {
            'restaurant': restaurant,
            'waiter_staff': waiter_staff,
            'orders_with_timeline': orders_with_timeline,
            'ready_items': ready_items,
        }
        
        return render(request, 'restaurants/waiter_orders_timeline.html', context)
        
    except Exception as e:
        logger.error(f"Error en waiter_orders_timeline: {e}")
        messages.error(request, f'Error cargando timeline de órdenes: {e}')
        return redirect('restaurants:home', tenant_slug=tenant_slug)


def calculate_area_progress(items):
    """Calcular progreso de un área específica"""
    if not items:
        return {
            'total': 0,
            'pending': 0,
            'in_progress': 0,
            'ready': 0,
            'percentage': 0
        }
    
    total = len(items)
    pending = len([i for i in items if i.status in ['pending', 'confirmed']])
    in_progress = len([i for i in items if i.is_in_preparation])
    ready = len([i for i in items if i.is_ready_for_service or i.status == 'served'])
    
    percentage = (ready / total * 100) if total > 0 else 0
    
    return {
        'total': total,
        'pending': pending,
        'in_progress': in_progress,
        'ready': ready,
        'percentage': round(percentage, 1)
    }


def determine_order_status(order, items_by_area):
    """Determinar estado general de la orden basado en items"""
    all_items = []
    for area_items in items_by_area.values():
        all_items.extend(area_items)
    
    if not all_items:
        return 'no_items'
    
    if all(item.status == 'served' for item in all_items):
        return 'completed'
    elif any(item.is_ready_for_service for item in all_items):
        return 'partial_ready'
    elif any(item.is_in_preparation for item in all_items):
        return 'in_progress'
    else:
        return 'pending'


def can_serve_order(items_by_area):
    """Verificar si la orden tiene items listos para servir"""
    all_items = []
    for area_items in items_by_area.values():
        all_items.extend(area_items)
    
    return any(item.is_ready_for_service for item in all_items)


@login_required
@require_POST
def serve_item(request, tenant_slug, item_id):
    """
    Marcar item como servido por el mesero
    """
    try:
        restaurant = request.restaurant
        waiter_staff = get_object_or_404(WaiterStaff, restaurant=restaurant, user=request.user)
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id, 
            order__restaurant=restaurant
        )
        
        if item.mark_served():
            # 🆕 FASE 2: Notificación granular cuando se sirve
            try:
                from .granular_notifications import GranularNotificationService
                GranularNotificationService.notify_order_served(item)
            except Exception as e:
                logger.error(f"Error en notificación de item servido: {e}")
            
            # Log de la acción
            logger.info(f"Item {item.id} servido por {waiter_staff.full_name}")
            
            # Verificar si toda la orden está servida
            order = item.order
            all_items_served = all(
                i.status == 'served' for i in order.items.all()
            )
            
            if all_items_served:
                order.status = 'delivered'
                order.delivered_at = timezone.now()
                order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{item.menu_item.name} servido correctamente',
                'item_served': True,
                'order_completed': all_items_served,
                'order_number': order.order_number,
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No se puede servir este item en su estado actual'
            })
            
    except Exception as e:
        logger.error(f"Error sirviendo item: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def order_detail_timeline(request, tenant_slug, order_id):
    """
    Vista detallada del timeline de una orden específica
    """
    try:
        restaurant = request.restaurant
        waiter_staff = get_object_or_404(WaiterStaff, restaurant=restaurant, user=request.user)
        
        order = get_object_or_404(
            Order, 
            id=order_id, 
            restaurant=restaurant
        )
        
        # Obtener todos los items con su timeline
        items_with_timeline = []
        for item in order.items.all().select_related('menu_item'):
            timeline_events = build_item_timeline(item)
            items_with_timeline.append({
                'item': item,
                'timeline': timeline_events,
                'progress_percentage': calculate_item_progress(item)
            })
        
        context = {
            'restaurant': restaurant,
            'waiter_staff': waiter_staff,
            'order': order,
            'items_with_timeline': items_with_timeline,
        }
        
        return render(request, 'restaurants/order_detail_timeline.html', context)
        
    except Exception as e:
        logger.error(f"Error en order_detail_timeline: {e}")
        messages.error(request, f'Error cargando detalle de orden: {e}')
        return redirect('restaurants:waiter_orders_timeline', tenant_slug=tenant_slug)


def build_item_timeline(item):
    """Construir timeline de eventos para un item"""
    events = []
    
    # Evento de creación
    events.append({
        'timestamp': item.created_at,
        'event': 'created',
        'description': f'Item agregado al pedido',
        'status': 'completed'
    })
    
    # Evento de confirmación
    if item.status != 'pending':
        events.append({
            'timestamp': item.created_at,  # Asumimos confirmación inmediata por ahora
            'event': 'confirmed',
            'description': f'Confirmado para {item.get_responsible_area_display()}',
            'status': 'completed'
        })
    
    # Evento de inicio de preparación
    if item.preparation_started_at:
        events.append({
            'timestamp': item.preparation_started_at,
            'event': 'preparation_started',
            'description': 'Preparación iniciada',
            'status': 'completed'
        })
    
    # Evento de finalización
    if item.preparation_completed_at:
        events.append({
            'timestamp': item.preparation_completed_at,
            'event': 'preparation_completed',
            'description': 'Listo para servir',
            'status': 'completed'
        })
    
    # Evento de servido
    if item.served_at:
        events.append({
            'timestamp': item.served_at,
            'event': 'served',
            'description': 'Servido al cliente',
            'status': 'completed'
        })
    
    return events


def calculate_item_progress(item):
    """Calcular porcentaje de progreso de un item"""
    status_progress = {
        'pending': 0,
        'confirmed': 20,
        'preparing_kitchen': 40,
        'cooking': 60,
        'plating': 80,
        'kitchen_ready': 90,
        'preparing_bar': 40,
        'mixing': 70,
        'bar_ready': 90,
        'ready': 95,
        'served': 100,
        'cancelled': 0,
    }
    
    return status_progress.get(item.status, 0)


def waiter_items_api(request, tenant_slug):
    """
    API para obtener estado actualizado de items para meseros
    """
    try:
        restaurant = request.restaurant
        
        # Items listos para servir
        ready_items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            status__in=['kitchen_ready', 'bar_ready', 'ready']
        ).select_related('order', 'menu_item')
        
        items_data = []
        for item in ready_items:
            items_data.append({
                'id': item.id,
                'menu_item_name': item.menu_item.name,
                'quantity': item.quantity,
                'status': item.status,
                'status_display': item.get_status_display(),
                'order_number': item.order.order_number,
                'table_number': item.order.table.number if item.order.table else None,
                'preparation_completed_at': item.preparation_completed_at.isoformat() if item.preparation_completed_at else None,
                'ready_time_minutes': calculate_ready_time_minutes(item),
            })
        
        return JsonResponse({
            'success': True,
            'ready_items': items_data,
            'count': len(items_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def calculate_ready_time_minutes(item):
    """Calcular cuántos minutos lleva listo un item"""
    if not item.preparation_completed_at:
        return 0
    
    delta = timezone.now() - item.preparation_completed_at
    return int(delta.total_seconds() / 60) 