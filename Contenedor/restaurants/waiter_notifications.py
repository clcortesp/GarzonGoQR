from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import WaiterNotification, Waiter, Table
import logging

logger = logging.getLogger(__name__)


class WaiterNotificationService:
    """
    Servicio para manejar notificaciones a garzones
    """
    
    @staticmethod
    def notify_new_order(order):
        """
        Notificar a un garzón sobre un nuevo pedido
        """
        if not order.table or not order.table.assigned_waiter:
            logger.warning(f"Pedido {order.order_number} sin mesa asignada o sin garzón")
            return None
        
        waiter = order.table.assigned_waiter
        
        # Verificar si el garzón está disponible
        if not waiter.is_available or not waiter.is_working_hours:
            logger.info(f"Garzón {waiter.full_name} no disponible, buscando alternativo")
            # Buscar garzón alternativo
            waiter = WaiterNotificationService._find_alternative_waiter(order.table)
            if not waiter:
                logger.error(f"No se encontró garzón disponible para mesa {order.table.number}")
                return None
        
        # Crear notificación
        notification = WaiterNotification.objects.create(
            waiter=waiter,
            table=order.table,
            order=order,
            notification_type='new_order',
            title=f'Nuevo pedido - Mesa {order.table.number}',
            message=f'Cliente: {order.customer_name}\nPedido: {order.order_number}\nTotal: ${order.total_amount}',
            priority=2,  # Alta prioridad para nuevos pedidos
            metadata={
                'order_total': str(order.total_amount),
                'customer_name': order.customer_name,
                'order_type': order.order_type,
                'items_count': order.total_items,
            }
        )
        
        # Enviar notificación por email si está habilitado
        if waiter.notification_email:
            WaiterNotificationService._send_email_notification(notification)
        
        # Aquí puedes agregar notificaciones push, SMS, etc.
        
        # Actualizar actividad del garzón
        waiter.update_activity()
        
        return notification
    
    @staticmethod
    def notify_order_ready(order):
        """
        Notificar cuando un pedido está listo para servir
        """
        if not order.table or not order.table.assigned_waiter:
            return None
        
        waiter = order.table.assigned_waiter
        
        notification = WaiterNotification.objects.create(
            waiter=waiter,
            table=order.table,
            order=order,
            notification_type='order_ready',
            title=f'Pedido listo - Mesa {order.table.number}',
            message=f'El pedido {order.order_number} está listo para servir',
            priority=3,  # Urgente - el pedido se está enfriando
            metadata={
                'order_number': order.order_number,
                'ready_time': timezone.now().isoformat(),
            }
        )
        
        if waiter.notification_email:
            WaiterNotificationService._send_email_notification(notification)
        
        return notification
    
    @staticmethod
    def notify_customer_request(table, request_type='general', message=''):
        """
        Notificar solicitud específica del cliente
        """
        if not table.assigned_waiter:
            return None
        
        waiter = table.assigned_waiter
        
        notification = WaiterNotification.objects.create(
            waiter=waiter,
            table=table,
            notification_type='customer_request',
            title=f'Solicitud Mesa {table.number}',
            message=message or 'El cliente necesita asistencia',
            priority=2,
            metadata={
                'request_type': request_type,
                'timestamp': timezone.now().isoformat(),
            }
        )
        
        return notification
    
    @staticmethod
    def _find_alternative_waiter(table):
        """
        Buscar un garzón alternativo disponible
        """
        # Buscar garzones activos y disponibles del mismo restaurante
        alternative_waiters = Waiter.objects.filter(
            restaurant=table.restaurant,
            status='active',
            is_available=True
        ).exclude(
            id=table.assigned_waiter.id if table.assigned_waiter else None
        )
        
        # Filtrar por horario de trabajo
        available_waiters = [w for w in alternative_waiters if w.is_working_hours]
        
        if available_waiters:
            # Devolver el que tenga menos mesas asignadas
            return min(available_waiters, key=lambda w: w.assigned_tables_count)
        
        return None
    
    @staticmethod
    def _send_email_notification(notification):
        """
        Enviar notificación por email
        """
        try:
            subject = f"[{notification.table.restaurant.name}] {notification.title}"
            
            context = {
                'notification': notification,
                'waiter': notification.waiter,
                'table': notification.table,
                'restaurant': notification.table.restaurant,
            }
            
            html_message = render_to_string('emails/waiter_notification.html', context)
            plain_message = render_to_string('emails/waiter_notification.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.waiter.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email enviado a {notification.waiter.user.email} para {notification.title}")
            
        except Exception as e:
            logger.error(f"Error enviando email a {notification.waiter.user.email}: {str(e)}")
    
    @staticmethod
    def get_waiter_notifications(waiter, unread_only=False):
        """
        Obtener notificaciones de un garzón
        """
        notifications = WaiterNotification.objects.filter(waiter=waiter)
        
        if unread_only:
            notifications = notifications.filter(status='pending')
        
        return notifications.order_by('-created_at')
    
    @staticmethod
    def mark_notifications_as_read(waiter, notification_ids=None):
        """
        Marcar notificaciones como leídas
        """
        notifications = WaiterNotification.objects.filter(
            waiter=waiter,
            status='pending'
        )
        
        if notification_ids:
            notifications = notifications.filter(id__in=notification_ids)
        
        updated_count = 0
        for notification in notifications:
            notification.mark_as_read()
            updated_count += 1
        
        return updated_count
    
    @staticmethod
    def get_waiter_stats(waiter, days=30):
        """
        Obtener estadísticas del garzón
        """
        from datetime import timedelta
        
        since_date = timezone.now() - timedelta(days=days)
        
        notifications = WaiterNotification.objects.filter(
            waiter=waiter,
            created_at__gte=since_date
        )
        
        orders = waiter.assigned_tables.filter(
            orders__created_at__gte=since_date
        ).values_list('orders', flat=True)
        
        return {
            'total_notifications': notifications.count(),
            'pending_notifications': notifications.filter(status='pending').count(),
            'response_rate': notifications.filter(status__in=['read', 'responded']).count() / max(notifications.count(), 1) * 100,
            'total_orders': len(set(orders)),
            'assigned_tables': waiter.assigned_tables_count,
            'last_activity': waiter.last_active,
        }


class WaiterDashboardService:
    """
    Servicio para el dashboard de garzones
    """
    
    @staticmethod
    def get_dashboard_data(waiter):
        """
        Obtener datos para el dashboard del garzón
        """
        # Notificaciones pendientes
        pending_notifications = WaiterNotificationService.get_waiter_notifications(
            waiter, unread_only=True
        )
        
        # Mesas asignadas con pedidos activos
        assigned_tables = waiter.assigned_tables.filter(is_active=True)
        active_orders = []
        
        for table in assigned_tables:
            table_orders = table.orders.filter(
                status__in=['pending', 'confirmed', 'preparing', 'ready']
            ).order_by('-created_at')
            
            if table_orders.exists():
                active_orders.extend(table_orders)
        
        # Estadísticas rápidas
        stats = WaiterNotificationService.get_waiter_stats(waiter)
        
        return {
            'waiter': waiter,
            'pending_notifications': pending_notifications,
            'assigned_tables': assigned_tables,
            'active_orders': active_orders,
            'stats': stats,
            'is_available': waiter.is_available,
            'is_working_hours': waiter.is_working_hours,
        } 