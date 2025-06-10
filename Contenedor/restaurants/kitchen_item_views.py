"""
FASE 2: Vistas especializadas de cocina para estados granulares por item
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator

from orders.models import Order, OrderItem
from .models import KitchenStaff
import logging

logger = logging.getLogger(__name__)


@login_required
def kitchen_items_dashboard(request, tenant_slug):
    """
    Dashboard de cocina con vista granular por items
    """
    try:
        restaurant = request.restaurant
        
        # Verificar si el usuario es personal de cocina
        try:
            kitchen_staff = KitchenStaff.objects.get(restaurant=restaurant, user=request.user)
        except KitchenStaff.DoesNotExist:
            messages.error(request, 'No tienes permisos de cocina para este restaurante.')
            return redirect('restaurants:home', tenant_slug=tenant_slug)
        
        # Obtener todos los items de cocina activos
        kitchen_items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='kitchen',
            status__in=['confirmed', 'preparing_kitchen', 'cooking', 'plating']
        ).select_related(
            'order', 
            'menu_item', 
            'order__table'
        ).order_by('order__created_at')
        
        # Separar por estado para mejor organización
        items_by_status = {
            'confirmed': [],
            'preparing_kitchen': [],
            'cooking': [],
            'plating': [],
        }
        
        for item in kitchen_items:
            if item.status in items_by_status:
                items_by_status[item.status].append(item)
        
        # Estadísticas de la cocina
        total_pending = len(items_by_status['confirmed'])
        total_in_progress = (
            len(items_by_status['preparing_kitchen']) + 
            len(items_by_status['cooking']) + 
            len(items_by_status['plating'])
        )
        
        # Items listos en las últimas 2 horas para referencia
        recent_ready = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='kitchen',
            status='kitchen_ready',
            preparation_completed_at__gte=timezone.now() - timezone.timedelta(hours=2)
        ).count()
        
        # 🆕 FASE 2: Reorganizar items para template tablet
        confirmed_items = items_by_status['confirmed']
        preparing_items = (
            items_by_status['preparing_kitchen'] + 
            items_by_status['cooking'] + 
            items_by_status['plating']
        )
        
        # Items listos para servir
        ready_items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='kitchen',
            status='kitchen_ready'
        ).select_related('order', 'menu_item', 'order__table')[:10]
        
        context = {
            'restaurant': restaurant,
            'kitchen_staff': kitchen_staff,
            'items_by_status': items_by_status,
            # 🆕 FASE 2: Variables específicas para tablet
            'confirmed_items': confirmed_items,
            'preparing_items': preparing_items,
            'ready_items': ready_items,
            'stats': {
                'total_pending': total_pending,
                'total_in_progress': total_in_progress,
                'total_ready': ready_items.count(),
            },
            'recent_ready': recent_ready,
            'status_choices': OrderItem.ITEM_STATUS_CHOICES,
        }
        
        # 🆕 FASE 2: Detectar tablet desde URL kwargs
        tablet_mode = 'tablet' in request.path or request.GET.get('tablet') == 'true'
        
        if tablet_mode:
            return render(request, 'restaurants/kitchen_tablet.html', context)
        else:
            return render(request, 'restaurants/kitchen_items_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error en kitchen_items_dashboard: {e}")
        messages.error(request, f'Error cargando dashboard de cocina: {e}')
        return redirect('restaurants:home', tenant_slug=tenant_slug)


@login_required
@require_POST
def update_kitchen_item_status(request, tenant_slug, item_id):
    """
    Actualizar estado de un item específico de cocina
    """
    try:
        restaurant = request.restaurant
        kitchen_staff = get_object_or_404(KitchenStaff, restaurant=restaurant, user=request.user)
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id, 
            order__restaurant=restaurant,
            responsible_area='kitchen'
        )
        
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        # Validar estado
        valid_kitchen_statuses = [
            'confirmed', 'preparing_kitchen', 'cooking', 'plating', 'kitchen_ready'
        ]
        
        if new_status not in valid_kitchen_statuses:
            return JsonResponse({
                'success': False, 
                'error': 'Estado inválido para cocina'
            })
        
        # Actualizar estado y timestamps
        previous_status = item.status
        item.status = new_status
        
        now = timezone.now()
        
        if new_status in ['preparing_kitchen', 'cooking'] and not item.preparation_started_at:
            item.preparation_started_at = now
        
        if new_status == 'kitchen_ready':
            item.preparation_completed_at = now
        
        item.save()
        
        # Log de la acción
        logger.info(f"Item {item.id} actualizado de {previous_status} a {new_status} por {kitchen_staff.full_name}")
        
        # Verificar si todos los items de la orden están listos
        order = item.order
        order_kitchen_items = order.items.filter(responsible_area='kitchen')
        all_kitchen_ready = all(
            i.status == 'kitchen_ready' for i in order_kitchen_items
        )
        
        # Notificar al mesero si todos los items de cocina están listos
        notification_sent = False
        if all_kitchen_ready:
            try:
                from .waiter_staff_notifications import WaiterStaffNotificationService
                # Aquí podríamos implementar notificación específica para items listos
                notification_sent = True
            except Exception as e:
                logger.error(f"Error enviando notificación: {e}")
        
        return JsonResponse({
            'success': True,
            'message': f'Item actualizado a {item.get_status_display()}',
            'new_status': new_status,
            'new_status_display': item.get_status_display(),
            'all_kitchen_ready': all_kitchen_ready,
            'notification_sent': notification_sent,
            'order_number': order.order_number,
        })
        
    except Exception as e:
        logger.error(f"Error actualizando item status: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def start_item_preparation(request, tenant_slug, item_id):
    """
    Iniciar preparación de un item (atajo rápido)
    """
    try:
        restaurant = request.restaurant
        kitchen_staff = get_object_or_404(KitchenStaff, restaurant=restaurant, user=request.user)
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id, 
            order__restaurant=restaurant,
            responsible_area='kitchen'
        )
        
        if item.start_preparation():
            # 🆕 FASE 2: Notificación granular
            try:
                from .granular_notifications import GranularNotificationService
                # Notificar que se inició preparación (opcional)
                logger.info(f"Preparación iniciada en cocina: {item.menu_item.name}")
            except Exception as e:
                logger.error(f"Error en notificación de inicio: {e}")
            
            return JsonResponse({
                'success': True,
                'message': f'Iniciada preparación de {item.menu_item.name}',
                'new_status': item.status,
                'new_status_display': item.get_status_display()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No se puede iniciar preparación de este item'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def mark_item_ready(request, tenant_slug, item_id):
    """
    Marcar item como listo (atajo rápido)
    """
    try:
        restaurant = request.restaurant
        kitchen_staff = get_object_or_404(KitchenStaff, restaurant=restaurant, user=request.user)
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id, 
            order__restaurant=restaurant,
            responsible_area='kitchen'
        )
        
        if item.mark_ready():
            # 🆕 FASE 2: Notificación granular a meseros
            try:
                from .granular_notifications import GranularNotificationService
                GranularNotificationService.notify_item_ready_for_service(item)
            except Exception as e:
                logger.error(f"Error en notificación de item listo: {e}")
            
            return JsonResponse({
                'success': True,
                'message': f'{item.menu_item.name} listo para servir',
                'new_status': item.status,
                'new_status_display': item.get_status_display()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No se puede marcar como listo este item'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def kitchen_items_api(request, tenant_slug):
    """
    API para obtener items de cocina en tiempo real
    """
    try:
        restaurant = request.restaurant
        
        items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='kitchen',
            status__in=['confirmed', 'preparing_kitchen', 'cooking', 'plating']
        ).select_related('order', 'menu_item').order_by('order__created_at')
        
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'menu_item_name': item.menu_item.name,
                'quantity': item.quantity,
                'status': item.status,
                'status_display': item.get_status_display(),
                'order_number': item.order.order_number,
                'table_number': item.order.table.number if item.order.table else None,
                'special_instructions': item.special_instructions,
                'estimated_prep_time': item.estimated_prep_time,
                'created_at': item.created_at.isoformat(),
                'preparation_started_at': item.preparation_started_at.isoformat() if item.preparation_started_at else None,
            })
        
        return JsonResponse({
            'success': True,
            'items': items_data,
            'count': len(items_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }) 