#!/usr/bin/env python
"""
Script para crear órdenes de prueba para probar el dashboard de pedidos
"""

import os
import sys
import django
from decimal import Decimal
from datetime import datetime, timedelta

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GarzonGoQR.settings')
django.setup()

from restaurants.models import Tenant, Restaurant
from menu.models import MenuItem
from orders.models import Order, OrderItem, OrderStatusHistory
from django.contrib.auth.models import User


def create_test_orders():
    """Crear órdenes de prueba"""
    
    print("🍕 Creando órdenes de prueba...")
    
    # Obtener el tenant y restaurant de pizzería luigi
    try:
        tenant = Tenant.objects.get(slug='pizzeria-luigi')
        restaurant = Restaurant.objects.get(tenant=tenant)
        print(f"✅ Encontrado restaurant: {restaurant.name}")
    except (Tenant.DoesNotExist, Restaurant.DoesNotExist):
        print("❌ No se encontró el tenant 'pizzeria-luigi'")
        return
    
    # Obtener algunos items del menú
    menu_items = MenuItem.objects.filter(tenant=tenant, is_available=True)[:3]
    if not menu_items:
        print("❌ No hay items disponibles en el menú")
        return
    
    print(f"✅ Encontrados {len(menu_items)} items del menú")
    
    # Crear órdenes de ejemplo
    orders_data = [
        {
            'customer_name': 'Juan Pérez',
            'customer_phone': '+57 300 123 4567',
            'customer_email': 'juan@email.com',
            'order_type': 'dine_in',
            'table_number': '5',
            'status': 'pending',
            'payment_method': 'cash',
            'customer_notes': 'Sin cebolla en la pizza',
        },
        {
            'customer_name': 'María García',
            'customer_phone': '+57 301 987 6543',
            'customer_email': 'maria@email.com',
            'order_type': 'delivery',
            'delivery_address': 'Calle 123 #45-67, Barrio Centro',
            'status': 'confirmed',
            'payment_method': 'card',
            'customer_notes': 'Apartamento 302, tocar timbre',
        },
        {
            'customer_name': 'Carlos Rodríguez',
            'customer_phone': '+57 302 456 7890',
            'order_type': 'takeaway',
            'status': 'preparing',
            'payment_method': 'transfer',
            'customer_notes': '',
        },
        {
            'customer_name': 'Ana López',
            'customer_phone': '+57 303 789 0123',
            'customer_email': 'ana@email.com',
            'order_type': 'dine_in',
            'table_number': '12',
            'status': 'ready',
            'payment_method': 'cash',
            'customer_notes': 'Para celíaco, sin gluten',
        },
        {
            'customer_name': 'Pedro Martínez',
            'customer_phone': '+57 304 123 4567',
            'order_type': 'delivery',
            'delivery_address': 'Carrera 7 #12-34, Zona Rosa',
            'status': 'delivered',
            'payment_method': 'card',
            'customer_notes': 'Casa azul con reja blanca',
        },
    ]
    
    created_orders = []
    
    for i, order_data in enumerate(orders_data):
        # Calcular precios
        subtotal = Decimal('35000') + (i * Decimal('5000'))  # Simular diferentes totales
        tax_amount = subtotal * Decimal('0.19')
        delivery_fee = Decimal('5000') if order_data['order_type'] == 'delivery' else Decimal('0')
        total_amount = subtotal + tax_amount + delivery_fee
        
        # Crear orden
        order = Order.objects.create(
            restaurant=restaurant,
            customer_name=order_data['customer_name'],
            customer_phone=order_data['customer_phone'],
            customer_email=order_data.get('customer_email', ''),
            order_type=order_data['order_type'],
            table_number=order_data.get('table_number'),
            delivery_address=order_data.get('delivery_address', ''),
            status=order_data['status'],
            payment_method=order_data['payment_method'],
            customer_notes=order_data['customer_notes'],
            subtotal=subtotal,
            tax_amount=tax_amount,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
        )
        
        # Agregar timestamps según el estado
        now = datetime.now()
        if order_data['status'] in ['confirmed', 'preparing', 'ready', 'delivered']:
            order.confirmed_at = now - timedelta(minutes=20 + i*10)
        if order_data['status'] in ['ready', 'delivered']:
            order.ready_at = now - timedelta(minutes=5 + i*5)
        if order_data['status'] == 'delivered':
            order.delivered_at = now - timedelta(minutes=i*2)
        
        order.save()
        
        # Crear items de la orden
        for j, menu_item in enumerate(menu_items):
            if j <= i:  # Simular diferentes cantidades de items
                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=1 + j,
                    unit_price=menu_item.price,
                    total_price=menu_item.price * (1 + j)
                )
        
        # Crear historial de estado
        OrderStatusHistory.objects.create(
            order=order,
            new_status=order_data['status'],
            notes=f'Orden creada automáticamente - Estado: {order_data["status"]}'
        )
        
        created_orders.append(order)
        print(f"✅ Creada orden #{order.order_number} - {order.customer_name} - {order.get_status_display()}")
    
    print(f"\n🎉 ¡Creadas {len(created_orders)} órdenes de prueba exitosamente!")
    print(f"📊 Puedes verlas en: http://localhost:8000/pizzeria-luigi/orders/dashboard/")
    
    return created_orders


if __name__ == '__main__':
    create_test_orders() 