# restaurants/waiter_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Waiter, WaiterNotification, Table
from .waiter_notifications import WaiterNotificationService, WaiterDashboardService


@login_required
def waiter_dashboard(request, tenant_slug):
    """
    Dashboard principal para garzones
    """
    print(f"🔍 waiter_dashboard called for user: {request.user.username}")
    print(f"🔍 tenant_slug: {tenant_slug}")
    
    try:
        restaurant = request.restaurant
        print(f"🔍 restaurant: {restaurant.name}")
        
        # Verificar si el usuario es un garzón (buscar en ambos modelos)
        waiter = None
        try:
            # Primero buscar en el modelo nuevo WaiterStaff
            from .models import WaiterStaff
            waiter = WaiterStaff.objects.get(restaurant=restaurant, user=request.user)
            print(f"✅ Found WaiterStaff: {waiter.full_name}")
        except WaiterStaff.DoesNotExist:
            print("❌ Not found in WaiterStaff, trying Waiter model...")
            try:
                # Si no está ahí, buscar en el modelo antiguo Waiter
                waiter = Waiter.objects.get(restaurant=restaurant, user=request.user)
                print(f"✅ Found Waiter: {waiter.full_name}")
            except Waiter.DoesNotExist:
                print("❌ Not found in Waiter model either!")
                messages.error(request, 'No tienes permisos de garzón para este restaurante.')
                return redirect('restaurants:home', tenant_slug=tenant_slug)
        
        # Obtener datos del dashboard de manera más robusta
        try:
            # Solo usar WaiterDashboardService si es un Waiter (modelo antiguo)
            if hasattr(waiter, '_meta') and waiter._meta.model_name == 'waiter':
                dashboard_data = WaiterDashboardService.get_dashboard_data(waiter)
            else:
                # Para WaiterStaff, crear datos básicos
                raise Exception("Using WaiterStaff - fallback to manual data")
        except Exception as service_error:
            print(f"Error en WaiterDashboardService: {service_error}")
            # Fallback: obtener datos básicos manualmente
            # Para WaiterStaff, las notificaciones no existen aún, así que usamos lista vacía
            if hasattr(waiter, '_meta') and waiter._meta.model_name == 'waiterstaff':
                pending_notifications = []  # WaiterStaff no tiene notificaciones aún
                assigned_tables = waiter.assigned_tables.filter(is_active=True) if hasattr(waiter, 'assigned_tables') else []
            else:
                # Para Waiter, intentar obtener notificaciones
                try:
                    pending_notifications = WaiterNotification.objects.filter(waiter=waiter, status='pending').order_by('-created_at')[:5]
                except:
                    pending_notifications = []
                assigned_tables = waiter.assigned_tables.filter(is_active=True) if hasattr(waiter, 'assigned_tables') else []
            
            # Obtener pedidos activos usando el nuevo servicio
            from .waiter_staff_notifications import WaiterStaffNotificationService
            active_orders = WaiterStaffNotificationService.get_orders_for_waiter(waiter)
            
            dashboard_data = {
                'waiter': waiter,
                'pending_notifications': pending_notifications,
                'assigned_tables': assigned_tables,
                'active_orders': active_orders,
                'stats': {'total_orders': active_orders.count()},
                'is_available': getattr(waiter, 'is_available', True),
                'is_working_hours': True,
            }
        
        # Preparar variables específicas para el template
        pending_orders = dashboard_data.get('active_orders', [])
        assigned_tables = dashboard_data.get('assigned_tables', [])
        recent_notifications = dashboard_data.get('pending_notifications', [])
        
        # Asegurar que sean listas si vienen como QuerySets
        if hasattr(pending_orders, 'all'):
            pending_orders = list(pending_orders.all())
        if hasattr(assigned_tables, 'all'):
            assigned_tables = list(assigned_tables.all())
        if hasattr(recent_notifications, 'all'):
            recent_notifications = list(recent_notifications.all())
        
        # Agregar información de pedidos activos y sesiones a las mesas
        from .table_session_manager import TableSessionManager
        
        tables_with_orders = []
        for table in assigned_tables:
            try:
                # Verificar si la mesa tiene pedidos activos
                if hasattr(table, 'orders'):
                    table_orders = [order for order in pending_orders if hasattr(order, 'table') and order.table.id == table.id]
                else:
                    table_orders = []
                table.has_active_orders = len(table_orders) > 0
                
                # Verificar si la mesa tiene sesión activa
                session_info = TableSessionManager._get_table_active_session(table)
                table.has_active_session = session_info is not None
                table.session_info = session_info
                
                tables_with_orders.append(table)
            except Exception as table_error:
                print(f"Error procesando mesa {table.id}: {table_error}")
                table.has_active_orders = False
                table.has_active_session = False
                table.session_info = None
                tables_with_orders.append(table)
        
        context = {
            'restaurant': restaurant,
            'tenant': restaurant.tenant,  # Agregar el tenant explícitamente
            'waiter': waiter,
            'pending_orders_count': len(pending_orders),
            'unread_notifications_count': len(recent_notifications),
            'assigned_tables_count': len(assigned_tables),
            'todays_orders_count': dashboard_data.get('stats', {}).get('total_orders', 0),
            'recent_notifications': recent_notifications,
            'recent_orders': pending_orders[:5],  # Solo los 5 más recientes
            'assigned_tables': tables_with_orders,
            'user_is_waiter': True,  # Indicar que es un garzón
        }
        
        return render(request, 'restaurants/waiter_dashboard.html', context)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error completo en waiter_dashboard: {error_details}")
        messages.error(request, f'Error cargando el dashboard: {e}')
        return redirect('restaurants:home', tenant_slug=tenant_slug)


@login_required
def waiter_notifications(request, tenant_slug):
    """
    Lista de notificaciones del garzón
    """
    try:
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        # Filtros
        status_filter = request.GET.get('status', 'all')
        notification_type = request.GET.get('type', 'all')
        
        notifications = WaiterNotificationService.get_waiter_notifications(waiter)
        
        if status_filter != 'all':
            notifications = notifications.filter(status=status_filter)
        
        if notification_type != 'all':
            notifications = notifications.filter(notification_type=notification_type)
        
        # Paginación
        paginator = Paginator(notifications, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'restaurant': restaurant,
            'tenant': restaurant.tenant,  # Agregar el tenant explícitamente
            'waiter': waiter,
            'page_obj': page_obj,
            'status_filter': status_filter,
            'notification_type': notification_type,
            'status_choices': WaiterNotification.STATUS_CHOICES,
            'type_choices': WaiterNotification.NOTIFICATION_TYPES,
            'user_is_waiter': True,  # Indicar que es un garzón
        }
        
        return render(request, 'restaurants/waiter_notifications.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando notificaciones: {e}')
        return redirect('restaurants:waiter_dashboard', tenant_slug=tenant_slug)


@login_required
@require_POST
def mark_notification_read(request, tenant_slug, notification_id):
    """
    Marcar una notificación como leída (AJAX)
    """
    try:
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        notification = get_object_or_404(
            WaiterNotification, 
            id=notification_id, 
            waiter=waiter
        )
        
        notification.mark_as_read()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificación marcada como leída'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def mark_notification_responded(request, tenant_slug, notification_id):
    """
    Marcar una notificación como respondida (AJAX)
    """
    try:
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        notification = get_object_or_404(
            WaiterNotification, 
            id=notification_id, 
            waiter=waiter
        )
        
        notification.mark_as_responded()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificación marcada como respondida'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def mark_all_notifications_read(request, tenant_slug):
    """
    Marcar todas las notificaciones pendientes como leídas (AJAX)
    """
    try:
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        updated_count = WaiterNotificationService.mark_notifications_as_read(waiter)
        
        return JsonResponse({
            'success': True,
            'message': f'{updated_count} notificaciones marcadas como leídas'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def waiter_tables(request, tenant_slug):
    """
    Lista de mesas asignadas al garzón
    """
    try:
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        assigned_tables = waiter.assigned_tables.filter(is_active=True).order_by('number')
        
        # Agregar información de pedidos activos para cada mesa
        tables_with_orders = []
        for table in assigned_tables:
            active_orders = table.orders.filter(
                status__in=['pending', 'confirmed', 'preparing', 'ready']
            ).order_by('-created_at')
            
            tables_with_orders.append({
                'table': table,
                'active_orders': active_orders,
                'has_active_orders': active_orders.exists()
            })
        
        context = {
            'restaurant': restaurant,
            'tenant': restaurant.tenant,  # Agregar el tenant explícitamente
            'waiter': waiter,
            'tables_with_orders': tables_with_orders,
            'user_is_waiter': True,  # Indicar que es un garzón
        }
        
        return render(request, 'restaurants/waiter_tables.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando mesas: {e}')
        return redirect('restaurants:waiter_dashboard', tenant_slug=tenant_slug)


@login_required
@require_POST
def update_waiter_status(request, tenant_slug):
    """
    Actualizar estado del garzón (disponible/no disponible) (AJAX)
    """
    try:
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        new_status = request.POST.get('status')
        is_available = request.POST.get('is_available', 'false').lower() == 'true'
        
        if new_status and new_status in dict(Waiter.STATUS_CHOICES):
            waiter.status = new_status
        
        waiter.is_available = is_available
        waiter.save()
        
        # Actualizar actividad
        waiter.update_activity()
        
        return JsonResponse({
            'success': True,
            'message': 'Estado actualizado correctamente',
            'new_status': waiter.get_status_display(),
            'is_available': waiter.is_available
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def request_customer_assistance(request, tenant_slug, table_id):
    """
    Permitir al cliente solicitar asistencia desde la mesa (AJAX)
    """
    try:
        restaurant = request.restaurant
        table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
        
        request_type = request.POST.get('request_type', 'general')
        message = request.POST.get('message', 'El cliente solicita asistencia')
        
        # Crear notificación para el garzón
        notification = WaiterNotificationService.notify_customer_request(
            table, request_type, message
        )
        
        if notification:
            return JsonResponse({
                'success': True,
                'message': 'Solicitud enviada al garzón asignado'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No hay garzón asignado a esta mesa'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def waiter_stats_api(request, tenant_slug):
    """
    API para obtener estadísticas del garzón (para gráficos)
    """
    try:
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        # Obtener estadísticas
        days = int(request.GET.get('days', 30))
        stats = WaiterNotificationService.get_waiter_stats(waiter, days)
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def waiter_end_table_session(request, tenant_slug):
    """
    Permitir que un garzón finalice la sesión de una mesa específica
    """
    try:
        from .table_session_manager import TableSessionManager
        import json
        
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        # Obtener datos del request
        data = json.loads(request.body)
        table_id = data.get('table_id')
        reason = data.get('reason', 'Finalizada por garzón')
        
        if not table_id:
            return JsonResponse({
                'success': False,
                'error': 'ID de mesa requerido'
            })
        
        # Obtener la mesa
        table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
        
        # Finalizar sesión
        success, message = TableSessionManager.waiter_end_table_session(waiter, table, reason)
        
        if success:
            # Crear notificación para el garzón
            try:
                WaiterNotification.objects.create(
                    waiter=waiter,
                    table=table,
                    notification_type='table_call',
                    title=f'Mesa {table.number} liberada',
                    message=f'Has finalizado la sesión de {table.display_name}. Mesa lista para nuevos clientes.',
                    priority=1,
                    status='read',  # Ya está "leída" porque la acción la hizo el garzón
                    metadata={
                        'action': 'session_ended_by_waiter',
                        'reason': reason,
                        'timestamp': timezone.now().isoformat()
                    }
                )
            except Exception as notification_error:
                print(f"Error creando notificación: {notification_error}")
            
            return JsonResponse({
                'success': True,
                'message': message
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Datos JSON inválidos'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        })


@login_required
def waiter_table_sessions_status(request, tenant_slug):
    """
    API mejorada para obtener estado de sesiones de mesas y pedidos en tiempo real
    """
    try:
        from .table_session_manager import TableSessionManager
        from django.core.cache import cache
        
        restaurant = request.restaurant
        waiter = get_object_or_404(Waiter, restaurant=restaurant, user=request.user)
        
        # Obtener mesas asignadas
        assigned_tables = waiter.assigned_tables.filter(is_active=True).order_by('number')
        
        tables_status = []
        for table in assigned_tables:
            # 1. Verificar sesión activa real
            recent_scan = table.scan_logs.filter(
                scanned_at__gte=timezone.now() - timedelta(minutes=60),
                ip_address__isnull=False
            ).exclude(ip_address="WAITER_CLEANUP").order_by('-scanned_at').first()
            
            # 2. Verificar si fue invalidada por garzón
            invalidation_key = f"table_invalidated_{table.id}"
            invalidation_data = cache.get(invalidation_key)
            was_invalidated = invalidation_data is not None
            
            has_active_session = bool(recent_scan and not was_invalidated)
            session_info = None
            
            if has_active_session and recent_scan:
                time_diff = timezone.now() - recent_scan.scanned_at
                minutes_ago = int(time_diff.total_seconds() // 60)
                session_info = {
                    'scan_time': recent_scan.scanned_at.isoformat(),
                    'time_ago': minutes_ago,
                    'ip_address': recent_scan.ip_address[:12] + "..." if len(recent_scan.ip_address) > 12 else recent_scan.ip_address,
                    'time_ago_text': f"{minutes_ago} min" if minutes_ago > 0 else "Recién conectado"
                }
            
            # 3. Contar pedidos nuevos/pendientes (últimas 2 horas)
            pending_orders = table.orders.filter(
                status__in=['pending', 'preparing'],
                created_at__gte=timezone.now() - timedelta(hours=2)
            ).count()
            
            # 4. Pedidos listos para entregar
            ready_orders = table.orders.filter(
                status='ready',
                created_at__gte=timezone.now() - timedelta(hours=4)
            ).count()
            
            # 5. Último pedido información
            last_order = table.orders.filter(
                created_at__gte=timezone.now() - timedelta(hours=4)
            ).order_by('-created_at').first()
            
            last_order_info = None
            if last_order:
                time_diff = timezone.now() - last_order.created_at
                minutes_ago = int(time_diff.total_seconds() // 60)
                last_order_info = {
                    'id': last_order.id,
                    'status': last_order.status,
                    'status_display': last_order.get_status_display(),
                    'total': float(last_order.total_amount),
                    'minutes_ago': minutes_ago,
                    'items_count': last_order.items.count(),
                    'time_text': f"hace {minutes_ago} min" if minutes_ago > 0 else "Recién"
                }
            
            # 6. Información de invalidación si existe
            invalidation_info = None
            if was_invalidated and invalidation_data:
                invalidation_info = {
                    'waiter_name': invalidation_data.get('waiter_name'),
                    'reason': invalidation_data.get('reason'),
                    'sessions_ended': invalidation_data.get('sessions_ended', 0)
                }
            
            table_data = {
                'id': table.id,
                'number': table.number,
                'name': table.display_name,
                'has_active_session': has_active_session,
                'session_info': session_info,
                'pending_orders_count': pending_orders,
                'ready_orders_count': ready_orders,
                'last_order': last_order_info,
                'was_invalidated': was_invalidated,
                'invalidation_info': invalidation_info,
                'needs_attention': pending_orders > 0 or ready_orders > 0
            }
            
            tables_status.append(table_data)
        
        return JsonResponse({
            'success': True,
            'tables': tables_status,
            'timestamp': timezone.now().isoformat(),
            'waiter_name': waiter.full_name
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }) 