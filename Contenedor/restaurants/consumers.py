import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Restaurant, Waiter

class WaiterDashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extraer parámetros de la URL
        self.tenant_slug = self.scope['url_route']['kwargs']['tenant_slug']
        self.waiter_id = self.scope['url_route']['kwargs']['waiter_id']
        
        # Crear nombre del grupo para este garzón
        self.waiter_group_name = f'waiter_{self.tenant_slug}_{self.waiter_id}'
        
        print(f"🔌 WebSocket conectando: {self.waiter_group_name}")
        
        # Verificar que el garzón existe
        waiter = await self.get_waiter()
        if not waiter:
            print(f"❌ Garzón {self.waiter_id} no encontrado en {self.tenant_slug}")
            await self.close()
            return
        
        # Unirse al grupo del garzón
        await self.channel_layer.group_add(
            self.waiter_group_name,
            self.channel_name
        )
        
        # Aceptar la conexión WebSocket
        await self.accept()
        
        print(f"✅ WebSocket conectado: {self.waiter_group_name}")
        
        # Enviar datos iniciales
        await self.send_initial_data()

    async def disconnect(self, close_code):
        print(f"🔌 WebSocket desconectando: {self.waiter_group_name} (código: {close_code})")
        
        # Salir del grupo del garzón
        await self.channel_layer.group_discard(
            self.waiter_group_name,
            self.channel_name
        )

    # Recibir mensaje del WebSocket
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            print(f"📨 Mensaje recibido: {message_type}")
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
            elif message_type == 'mark_notification_read':
                notification_id = text_data_json.get('notification_id')
                await self.mark_notification_read(notification_id)
            elif message_type == 'update_waiter_status':
                status = text_data_json.get('status')
                await self.update_waiter_status(status)
                
        except json.JSONDecodeError:
            print(f"❌ Error decodificando JSON: {text_data}")

    # Enviar notificación nueva
    async def new_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))

    # Enviar actualización de pedido
    async def order_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'order_update',
            'order': event['order']
        }))

    # Enviar actualización de estadísticas
    async def stats_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'stats': event['stats']
        }))

    # Métodos de base de datos (síncronos convertidos a asíncronos)
    @database_sync_to_async
    def get_waiter(self):
        try:
            from django.apps import apps
            Restaurant = apps.get_model('restaurants', 'Restaurant')
            Waiter = apps.get_model('restaurants', 'Waiter')
            
            restaurant = Restaurant.objects.get(slug=self.tenant_slug)
            waiter = Waiter.objects.get(id=self.waiter_id, restaurant=restaurant)
            return waiter
        except Exception as e:
            print(f"❌ Error obteniendo garzón: {e}")
            return None

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        try:
            # TODO: Implementar cuando tengamos modelo de notificaciones
            print(f"✅ Notificación {notification_id} marcada como leída")
            return True
        except Exception as e:
            print(f"❌ Error marcando notificación: {e}")
            return False

    @database_sync_to_async
    def update_waiter_status(self, status):
        try:
            # TODO: Implementar actualización de estado del garzón
            print(f"✅ Estado del garzón actualizado a: {status}")
            return True
        except Exception as e:
            print(f"❌ Error actualizando estado: {e}")
            return False

    async def send_initial_data(self):
        """Enviar datos iniciales del dashboard"""
        # Datos de ejemplo por ahora
        initial_data = {
            'type': 'initial_data',
            'waiter': {
                'id': int(self.waiter_id),
                'full_name': 'Juan Pérez',
                'employee_id': 'GAR001',
                'status': 'active',
                'is_available': True
            },
            'stats': {
                'pending_orders_count': 2,
                'unread_notifications_count': 1,
                'assigned_tables_count': 4,
                'todays_orders_count': 8,
                'active_sessions_count': 2,
                'total_revenue_today': 25000
            },
            'notifications': [
                {
                    'id': 1,
                    'type': 'new_order',
                    'title': 'Nuevo Pedido',
                    'message': 'Mesa 3 - Pedido recibido',
                    'timestamp': '2024-01-20T15:30:00Z',
                    'priority': 2
                }
            ]
        }
        
        await self.send(text_data=json.dumps(initial_data)) 