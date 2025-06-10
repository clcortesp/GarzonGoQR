#!/usr/bin/env python
"""
Script para configurar mesas y meseros
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'garzongoqr.settings')
django.setup()

from restaurants.models import *
from django.contrib.auth.models import User
from orders.models import Order

def main():
    print("=== CONFIGURACIÓN DEL SISTEMA DE MESEROS ===\n")
    
    # 1. Buscar restaurante
    restaurant = Restaurant.objects.first()
    if not restaurant:
        print("❌ No hay restaurantes configurados")
        return
    
    print(f"🏪 Restaurante: {restaurant.name}")
    
    # 2. Buscar mesero
    try:
        user = User.objects.get(username='mesero1')
        waiter_staff = WaiterStaff.objects.get(user=user, restaurant=restaurant)
        print(f"👤 Mesero encontrado: {waiter_staff.full_name}")
    except (User.DoesNotExist, WaiterStaff.DoesNotExist):
        print("❌ Mesero 'mesero1' no encontrado")
        return
    
    # 3. Verificar mesas
    tables = Table.objects.filter(restaurant=restaurant)
    print(f"\n🪑 Mesas disponibles: {tables.count()}")
    
    if not tables.exists():
        print("❌ No hay mesas creadas. Creando mesas de ejemplo...")
        # Crear mesas de ejemplo
        for i in range(1, 6):
            Table.objects.create(
                restaurant=restaurant,
                number=str(i),
                name=f"Mesa {i}",
                capacity=4
            )
        tables = Table.objects.filter(restaurant=restaurant)
        print(f"✅ Creadas {tables.count()} mesas")
    
    # 4. Asignar mesero a mesas
    assigned_count = 0
    for table in tables:
        print(f"  - Mesa {table.number}: {table.display_name}")
        if not table.assigned_waiter_staff:
            table.assigned_waiter_staff = waiter_staff
            table.save()
            assigned_count += 1
            print(f"    ✅ Asignada a {waiter_staff.full_name}")
        else:
            print(f"    ⚠️  Ya asignada a {table.assigned_staff_name}")
    
    print(f"\n📊 RESUMEN:")
    print(f"   - Mesas asignadas al mesero: {assigned_count}")
    
    # 5. Verificar pedidos existentes
    orders = Order.objects.filter(restaurant=restaurant).order_by('-created_at')
    print(f"   - Pedidos en el sistema: {orders.count()}")
    
    if orders.exists():
        print("\n📦 PEDIDOS RECIENTES:")
        for order in orders[:5]:
            mesa = f"Mesa {order.table.number}" if order.table else "Sin mesa"
            print(f"   - {order.order_number}: {order.status} - {mesa} - ${order.total_amount}")
    
    # 6. Verificar pedidos asignados al mesero
    from restaurants.waiter_staff_notifications import WaiterStaffNotificationService
    waiter_orders = WaiterStaffNotificationService.get_orders_for_waiter(waiter_staff)
    print(f"\n🍽️  Pedidos asignados al mesero: {waiter_orders.count()}")
    
    if waiter_orders.exists():
        print("   PEDIDOS ACTIVOS:")
        for order in waiter_orders:
            print(f"   - {order.order_number}: {order.status} - Mesa {order.table.number}")
    else:
        print("   ⚠️  No hay pedidos activos asignados al mesero")
        print("   💡 Crea un pedido desde el QR para verlo en el dashboard")
    
    print(f"\n🎯 PRÓXIMOS PASOS:")
    print(f"   1. Accede al dashboard: http://localhost:8000/{restaurant.tenant.slug}/waiter/")
    print(f"   2. Escanea un QR de mesa para hacer un pedido")
    print(f"   3. El pedido aparecerá automáticamente en el dashboard del mesero")

if __name__ == "__main__":
    main() 