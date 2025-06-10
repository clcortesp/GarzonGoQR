"""
FASE 2: Sistema de Notificaciones Granulares en Tiempo Real
"""
import logging
from django.utils import timezone
from django.contrib.auth.models import User
from .models import WaiterStaff, KitchenStaff, BarStaff
from .waiter_notifications import WaiterNotificationService

logger = logging.getLogger(__name__)


class GranularNotificationService:
    """
    Servicio de notificaciones granulares para estados de items
    """
    
    @staticmethod
    def notify_item_ready_for_preparation(order_item):
        """
        Notificar cuando un item está listo para iniciar preparación
        """
        try:
            if order_item.responsible_area == 'kitchen':
                GranularNotificationService._notify_kitchen_staff(
                    order_item.order.restaurant,
                    f"🔸 Nuevo item para cocina: {order_item.quantity}x {order_item.menu_item.name}",
                    f"Orden {order_item.order.order_number} - Mesa {order_item.order.table.number if order_item.order.table else 'N/A'}",
                    'new_item'
                )
            
            elif order_item.responsible_area == 'bar':
                GranularNotificationService._notify_bar_staff(
                    order_item.order.restaurant,
                    f"🍸 Nueva bebida para preparar: {order_item.quantity}x {order_item.menu_item.name}",
                    f"Orden {order_item.order.order_number} - Mesa {order_item.order.table.number if order_item.order.table else 'N/A'}",
                    'new_drink'
                )
            
            logger.info(f"Notificación enviada para item {order_item.id} - Área: {order_item.responsible_area}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de preparación: {e}")
    
    @staticmethod
    def notify_item_ready_for_service(order_item):
        """
        Notificar cuando un item está listo para servir
        """
        try:
            area_emoji = "🍳" if order_item.responsible_area == 'kitchen' else "🍸"
            
            # Notificar a todos los meseros
            GranularNotificationService._notify_waiter_staff(
                order_item.order.restaurant,
                f"✅ {area_emoji} Item listo para servir",
                f"{order_item.quantity}x {order_item.menu_item.name} - Orden {order_item.order.order_number} - Mesa {order_item.order.table.number if order_item.order.table else 'N/A'}",
                'item_ready',
                priority='high'
            )
            
            logger.info(f"Notificación de item listo enviada: {order_item.id}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de item listo: {e}")
    
    @staticmethod
    def notify_order_served(order_item):
        """
        Notificar cuando un item ha sido servido
        """
        try:
            # Verificar si toda la orden está servida
            order = order_item.order
            all_items = order.items.all()
            served_items = [item for item in all_items if item.status == 'served']
            
            if len(served_items) == len(all_items):
                # Orden completamente servida
                GranularNotificationService._notify_all_staff(
                    order.restaurant,
                    f"✅ Orden completada y servida",
                    f"Orden {order.order_number} - Mesa {order.table.number if order.table else 'N/A'} completada exitosamente",
                    'order_served'
                )
                
                # Actualizar estado de la orden
                order.status = 'delivered'
                order.delivered_at = timezone.now()
                order.save()
            
            logger.info(f"Item servido notificado: {order_item.id}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de item servido: {e}")
    
    @staticmethod
    def notify_kitchen_delay(order_item, estimated_delay):
        """
        Notificar cuando hay retraso en cocina
        """
        try:
            GranularNotificationService._notify_waiter_staff(
                order_item.order.restaurant,
                f"⚠️ Retraso en cocina",
                f"{order_item.menu_item.name} - Orden {order_item.order.order_number} - Retraso estimado: {estimated_delay} min",
                'kitchen_delay',
                priority='medium'
            )
            
        except Exception as e:
            logger.error(f"Error enviando notificación de retraso: {e}")
    
    @staticmethod
    def notify_bar_delay(order_item, estimated_delay):
        """
        Notificar cuando hay retraso en bar
        """
        try:
            GranularNotificationService._notify_waiter_staff(
                order_item.order.restaurant,
                f"⚠️ Retraso en bar",
                f"{order_item.menu_item.name} - Orden {order_item.order.order_number} - Retraso estimado: {estimated_delay} min",
                'bar_delay',
                priority='medium'
            )
            
        except Exception as e:
            logger.error(f"Error enviando notificación de retraso: {e}")
    
    @staticmethod
    def _notify_kitchen_staff(restaurant, title, message, notification_type):
        """
        Notificar específicamente al personal de cocina
        """
        try:
            kitchen_staff = KitchenStaff.objects.filter(
                restaurant=restaurant,
                is_active=True
            ).select_related('user')
            
            for staff in kitchen_staff:
                WaiterNotificationService.create_notification(
                    restaurant=restaurant,
                    user=staff.user,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority='medium'
                )
            
        except Exception as e:
            logger.error(f"Error notificando a cocina: {e}")
    
    @staticmethod
    def _notify_bar_staff(restaurant, title, message, notification_type):
        """
        Notificar específicamente al personal de bar
        """
        try:
            bar_staff = BarStaff.objects.filter(
                restaurant=restaurant,
                is_active=True
            ).select_related('user')
            
            for staff in bar_staff:
                WaiterNotificationService.create_notification(
                    restaurant=restaurant,
                    user=staff.user,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority='medium'
                )
            
        except Exception as e:
            logger.error(f"Error notificando a bar: {e}")
    
    @staticmethod
    def _notify_waiter_staff(restaurant, title, message, notification_type, priority='medium'):
        """
        Notificar específicamente a los meseros
        """
        try:
            waiter_staff = WaiterStaff.objects.filter(
                restaurant=restaurant,
                is_active=True
            ).select_related('user')
            
            for staff in waiter_staff:
                WaiterNotificationService.create_notification(
                    restaurant=restaurant,
                    user=staff.user,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority
                )
            
        except Exception as e:
            logger.error(f"Error notificando a meseros: {e}")
    
    @staticmethod
    def _notify_all_staff(restaurant, title, message, notification_type):
        """
        Notificar a todo el personal del restaurante
        """
        try:
            # Obtener todos los usuarios del staff
            all_staff_users = []
            
            # Kitchen staff
            kitchen_users = KitchenStaff.objects.filter(
                restaurant=restaurant, is_active=True
            ).values_list('user', flat=True)
            all_staff_users.extend(kitchen_users)
            
            # Bar staff
            bar_users = BarStaff.objects.filter(
                restaurant=restaurant, is_active=True
            ).values_list('user', flat=True)
            all_staff_users.extend(bar_users)
            
            # Waiter staff
            waiter_users = WaiterStaff.objects.filter(
                restaurant=restaurant, is_active=True
            ).values_list('user', flat=True)
            all_staff_users.extend(waiter_users)
            
            # Eliminar duplicados
            unique_users = list(set(all_staff_users))
            
            for user_id in unique_users:
                try:
                    user = User.objects.get(id=user_id)
                    WaiterNotificationService.create_notification(
                        restaurant=restaurant,
                        user=user,
                        title=title,
                        message=message,
                        notification_type=notification_type,
                        priority='low'
                    )
                except User.DoesNotExist:
                    continue
            
        except Exception as e:
            logger.error(f"Error notificando a todo el staff: {e}")


class ItemProgressTracker:
    """
    Tracker para monitorear progreso de items y detectar retrasos
    """
    
    @staticmethod
    def check_item_delays(restaurant):
        """
        Verificar items con retrasos y enviar notificaciones
        """
        try:
            from orders.models import OrderItem
            from datetime import timedelta
            
            now = timezone.now()
            delay_threshold = timedelta(minutes=10)  # 10 minutos de retraso
            
            # Items en preparación que están retrasados
            delayed_items = OrderItem.objects.filter(
                order__restaurant=restaurant,
                status__in=['preparing_kitchen', 'cooking', 'preparing_bar', 'mixing'],
                preparation_started_at__isnull=False,
                preparation_started_at__lt=now - delay_threshold
            )
            
            for item in delayed_items:
                delay_minutes = int((now - item.preparation_started_at).total_seconds() / 60)
                
                if item.responsible_area == 'kitchen':
                    GranularNotificationService.notify_kitchen_delay(item, delay_minutes)
                elif item.responsible_area == 'bar':
                    GranularNotificationService.notify_bar_delay(item, delay_minutes)
            
        except Exception as e:
            logger.error(f"Error verificando retrasos: {e}")
    
    @staticmethod
    def get_area_performance(restaurant, area, hours=24):
        """
        Obtener métricas de rendimiento de un área
        """
        try:
            from orders.models import OrderItem
            from datetime import timedelta
            
            since = timezone.now() - timedelta(hours=hours)
            
            items = OrderItem.objects.filter(
                order__restaurant=restaurant,
                responsible_area=area,
                preparation_completed_at__gte=since
            )
            
            if not items:
                return None
            
            # Calcular tiempos promedio
            total_prep_time = 0
            completed_items = 0
            
            for item in items:
                if item.preparation_started_at and item.preparation_completed_at:
                    prep_time = (item.preparation_completed_at - item.preparation_started_at).total_seconds() / 60
                    total_prep_time += prep_time
                    completed_items += 1
            
            avg_prep_time = total_prep_time / completed_items if completed_items > 0 else 0
            
            return {
                'area': area,
                'total_items': items.count(),
                'completed_items': completed_items,
                'avg_prep_time': round(avg_prep_time, 1),
                'efficiency': round((completed_items / items.count()) * 100, 1) if items.count() > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculando performance de {area}: {e}")
            return None 