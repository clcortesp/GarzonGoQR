"""
FASE 2: Vistas especializadas de bar para estados granulares por item
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages

from orders.models import Order, OrderItem
from .models import BarStaff
import logging

logger = logging.getLogger(__name__)


@login_required
def bar_items_dashboard(request, tenant_slug):
    """
    Dashboard de bar con vista granular por items de bebidas
    """
    try:
        restaurant = request.restaurant
        
        # Verificar si el usuario es personal de bar
        try:
            bar_staff = BarStaff.objects.get(restaurant=restaurant, user=request.user)
        except BarStaff.DoesNotExist:
            messages.error(request, 'No tienes permisos de bar para este restaurante.')
            return redirect('restaurants:home', tenant_slug=tenant_slug)
        
        # Obtener todos los items de bar activos
        bar_items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='bar',
            status__in=['confirmed', 'preparing_bar', 'mixing']
        ).select_related(
            'order', 
            'menu_item', 
            'order__table'
        ).order_by('order__created_at')
        
        # Separar por estado
        items_by_status = {
            'confirmed': [],
            'preparing_bar': [],
            'mixing': [],
        }
        
        for item in bar_items:
            if item.status in items_by_status:
                items_by_status[item.status].append(item)
        
        # Estadísticas del bar
        total_pending = len(items_by_status['confirmed'])
        total_in_progress = (
            len(items_by_status['preparing_bar']) + 
            len(items_by_status['mixing'])
        )
        
        # Items listos en la última hora
        recent_ready = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='bar',
            status='bar_ready',
            preparation_completed_at__gte=timezone.now() - timezone.timedelta(hours=1)
        ).count()
        
        # 🆕 FASE 2: Reorganizar items para template tablet
        confirmed_items = items_by_status['confirmed']
        preparing_items = (
            items_by_status['preparing_bar'] + 
            items_by_status['mixing']
        )
        
        # Items listos para servir
        ready_items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='bar',
            status='bar_ready'
        ).select_related('order', 'menu_item', 'order__table')[:10]
        
        context = {
            'restaurant': restaurant,
            'bar_staff': bar_staff,
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
            return render(request, 'restaurants/bar_tablet.html', context)
        else:
            return render(request, 'restaurants/bar_items_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error en bar_items_dashboard: {e}")
        messages.error(request, f'Error cargando dashboard de bar: {e}')
        return redirect('restaurants:home', tenant_slug=tenant_slug)


@login_required
@require_POST
def update_bar_item_status(request, tenant_slug, item_id):
    """
    Actualizar estado de un item específico del bar
    """
    try:
        restaurant = request.restaurant
        bar_staff = get_object_or_404(BarStaff, restaurant=restaurant, user=request.user)
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id, 
            order__restaurant=restaurant,
            responsible_area='bar'
        )
        
        new_status = request.POST.get('status')
        
        # Validar estado para bar
        valid_bar_statuses = [
            'confirmed', 'preparing_bar', 'mixing', 'bar_ready'
        ]
        
        if new_status not in valid_bar_statuses:
            return JsonResponse({
                'success': False, 
                'error': 'Estado inválido para bar'
            })
        
        # Actualizar estado y timestamps
        previous_status = item.status
        item.status = new_status
        
        now = timezone.now()
        
        if new_status in ['preparing_bar', 'mixing'] and not item.preparation_started_at:
            item.preparation_started_at = now
        
        if new_status == 'bar_ready':
            item.preparation_completed_at = now
        
        item.save()
        
        # Log de la acción
        logger.info(f"Item {item.id} actualizado de {previous_status} a {new_status} por {bar_staff.full_name}")
        
        # Verificar si todos los items del bar están listos
        order = item.order
        order_bar_items = order.items.filter(responsible_area='bar')
        all_bar_ready = all(
            i.status == 'bar_ready' for i in order_bar_items
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Item actualizado a {item.get_status_display()}',
            'new_status': new_status,
            'new_status_display': item.get_status_display(),
            'all_bar_ready': all_bar_ready,
            'order_number': order.order_number,
        })
        
    except Exception as e:
        logger.error(f"Error actualizando item status en bar: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def start_bar_item_preparation(request, tenant_slug, item_id):
    """
    Iniciar preparación de bebida (atajo rápido)
    """
    try:
        restaurant = request.restaurant
        bar_staff = get_object_or_404(BarStaff, restaurant=restaurant, user=request.user)
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id, 
            order__restaurant=restaurant,
            responsible_area='bar'
        )
        
        if item.start_preparation():
            return JsonResponse({
                'success': True,
                'message': f'Iniciada preparación de {item.menu_item.name}',
                'new_status': item.status,
                'new_status_display': item.get_status_display()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No se puede iniciar preparación de esta bebida'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def mark_bar_item_ready(request, tenant_slug, item_id):
    """
    Marcar bebida como lista (atajo rápido)
    """
    try:
        restaurant = request.restaurant
        bar_staff = get_object_or_404(BarStaff, restaurant=restaurant, user=request.user)
        
        item = get_object_or_404(
            OrderItem, 
            id=item_id, 
            order__restaurant=restaurant,
            responsible_area='bar'
        )
        
        if item.mark_ready():
            # 🆕 FASE 2: Notificación granular a meseros
            try:
                from .granular_notifications import GranularNotificationService
                GranularNotificationService.notify_item_ready_for_service(item)
            except Exception as e:
                logger.error(f"Error en notificación de bebida lista: {e}")
            
            return JsonResponse({
                'success': True,
                'message': f'{item.menu_item.name} listo para servir',
                'new_status': item.status,
                'new_status_display': item.get_status_display()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No se puede marcar como lista esta bebida'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def bar_items_api(request, tenant_slug):
    """
    API para obtener items del bar en tiempo real
    """
    try:
        restaurant = request.restaurant
        
        items = OrderItem.objects.filter(
            order__restaurant=restaurant,
            responsible_area='bar',
            status__in=['confirmed', 'preparing_bar', 'mixing']
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
                'item_description': item.item_description,
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