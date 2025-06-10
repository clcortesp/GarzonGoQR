from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import WaiterNotification, Waiter, WaiterStaff, Table
import logging

logger = logging.getLogger(__name__)


class WaiterStaffNotificationService:
    """
    Servicio para manejar notificaciones compatibles con WaiterStaff y Waiter
    """
    
    @staticmethod
    def notify_new_order(order):
        """
        Notificar a un mesero sobre un nuevo pedido (compatible con ambos modelos)
        """
        if not order.table:
            logger.warning(f"Pedido {order.order_number} sin mesa asignada")
            return None
        
        # Buscar mesero asignado (priorizar WaiterStaff sobre Waiter)
        waiter = WaiterStaffNotificationService._get_assigned_waiter(order.table)
        
        if not waiter:
            logger.warning(f"Mesa {order.table.number} sin mesero asignado, buscando alternativo")
            waiter = WaiterStaffNotificationService._find_alternative_waiter(order.table)
            if not waiter:
                logger.error(f"No se encontró mesero disponible para mesa {order.table.number}")
                return None
        
        # Verificar si el mesero está disponible
        if not waiter.is_available:
            logger.info(f"Mesero {waiter.full_name} no disponible, buscando alternativo")
            waiter = WaiterStaffNotificationService._find_alternative_waiter(order.table)
            if not waiter:
                logger.error(f"No se encontró mesero alternativo para mesa {order.table.number}")
                return None
        
        # Solo crear notificación si es un Waiter (modelo antiguo)
        # Para WaiterStaff, por ahora solo log la información
        if hasattr(waiter, '_meta') and waiter._meta.model_name == 'waiter':
            notification = WaiterNotification.objects.create(
                waiter=waiter,
                table=order.table,
                order=order,
                notification_type='new_order',
                title=f'Nuevo pedido - Mesa {order.table.number}',
                message=f'Cliente: {order.customer_name}\nPedido: {order.order_number}\nTotal: ${order.total_amount}',
                priority=2,
                metadata={
                    'order_total': str(order.total_amount),
                    'customer_name': order.customer_name,
                    'order_type': order.order_type,
                    'items_count': order.total_items,
                }
            )
            
            # Enviar notificación por email si está habilitado
            if waiter.notification_email:
                WaiterStaffNotificationService._send_email_notification_waiter(notification)
            
            logger.info(f"Notificación creada para Waiter {waiter.full_name}")
            return notification
        else:
            # Para WaiterStaff, solo logging por ahora
            logger.info(f"Nuevo pedido {order.order_number} asignado a WaiterStaff {waiter.full_name} en mesa {order.table.number}")
            
            # Simular notificación para compatibilidad
            class MockNotification:
                def __init__(self, waiter, order):
                    self.waiter = waiter
                    self.order = order
                    self.title = f'Nuevo pedido - Mesa {order.table.number}'
                    self.message = f'Cliente: {order.customer_name}\nPedido: {order.order_number}\nTotal: ${order.total_amount}'
            
            return MockNotification(waiter, order)
    
    @staticmethod
    def _get_assigned_waiter(table):
        """
        Obtener el mesero asignado a una mesa (priorizar WaiterStaff)
        """
        # Priorizar WaiterStaff sobre Waiter
        if table.assigned_waiter_staff:
            return table.assigned_waiter_staff
        elif table.assigned_waiter:
            return table.assigned_waiter
        return None
    
    @staticmethod
    def _find_alternative_waiter(table):
        """
        Buscar un mesero alternativo disponible (buscar en ambos modelos)
        """
        restaurant = table.restaurant
        
        # Buscar primero en WaiterStaff
        waiter_staff_list = WaiterStaff.objects.filter(
            restaurant=restaurant,
            status='active',
            is_available=True
        )
        
        for waiter in waiter_staff_list:
            if waiter.assigned_tables_count < waiter.max_tables_assigned:
                return waiter
        
        # Si no hay WaiterStaff disponible, buscar en Waiter
        waiter_list = Waiter.objects.filter(
            restaurant=restaurant,
            status='active',
            is_available=True

        )
        
        available_waiters = [w for w in waiter_list if w.is_working_hours]
        
        if available_waiters:
            return min(available_waiters, key=lambda w: w.assigned_tables_count)
        
        return None
    
    @staticmethod
    def _send_email_notification_waiter(notification):
        """
        Enviar notificación por email para Waiter
        """
        try:
            subject = f"[{notification.table.restaurant.name}] {notification.title}"
            
            context = {
                'notification': notification,
                'waiter': notification.waiter,
                'table': notification.table,
                'restaurant': notification.table.restaurant,
            }
            
            # Solo enviar si existe el template
            try:
                html_message = render_to_string('emails/waiter_notification.html', context)
                plain_message = render_to_string('emails/waiter_notification.txt', context)
                
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[notification.waiter.user.email],
                    html_message=html_message,
                    fail_silently=True,
                )
                
                logger.info(f"Email enviado a {notification.waiter.user.email}")
            except:
                logger.info(f"Email template no encontrado, omitiendo envío")
            
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
    
    @staticmethod
    def get_orders_for_waiter(waiter):
        """
        Obtener pedidos asignados a un mesero (compatible con ambos modelos)
        """
        from orders.models import Order
        
        # Si es WaiterStaff, buscar por assigned_waiter_staff
        if hasattr(waiter, '_meta') and waiter._meta.model_name == 'waiterstaff':
            # Buscar mesas asignadas a este WaiterStaff
            tables = Table.objects.filter(
                restaurant=waiter.restaurant,
                assigned_waiter_staff=waiter,
                is_active=True
            )
            
            # Buscar pedidos de esas mesas que estén activos
            orders = Order.objects.filter(
                table__in=tables,
                status__in=['pending', 'confirmed', 'preparing', 'ready']
            ).select_related('table', 'restaurant').prefetch_related('items').order_by('-created_at')
            
        else:
            # Para Waiter, usar sistema original
            tables = Table.objects.filter(
                restaurant=waiter.restaurant,
                assigned_waiter=waiter,
                is_active=True
            )
            
            orders = Order.objects.filter(
                table__in=tables,
                status__in=['pending', 'confirmed', 'preparing', 'ready']
            ).select_related('table', 'restaurant').prefetch_related('items').order_by('-created_at')
        
        return orders
    
    @staticmethod
    def get_notifications_for_waiter(waiter):
        """
        Obtener notificaciones para un mesero (solo para Waiter por ahora)
        """
        if hasattr(waiter, '_meta') and waiter._meta.model_name == 'waiter':
            return WaiterNotification.objects.filter(
                waiter=waiter,
                status='pending'
            ).order_by('-created_at')
        else:
            # Para WaiterStaff, retornar lista vacía por ahora
            return WaiterNotification.objects.none() 