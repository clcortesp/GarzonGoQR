#!/usr/bin/env python
"""
Script para crear datos de garzones de ejemplo
"""
import os
import sys
import django
from django.contrib.auth.models import User

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GarzonGoQR.settings')
django.setup()

from restaurants.models import Restaurant, Waiter, Table

def create_sample_waiters():
    """
    Crear garzones de ejemplo para pizzeria-luigi
    """
    try:
        # Obtener el restaurante pizzeria-luigi
        restaurant = Restaurant.objects.get(tenant__slug='pizzeria-luigi')
        print(f"🍕 Trabajando con {restaurant.name}")
        
        # Datos de garzones de ejemplo
        waiters_data = [
            {
                'first_name': 'Carlos',
                'last_name': 'Rodríguez',
                'username': 'carlos.garzon',
                'email': 'carlos@pizzerialuigi.com',
                'employee_id': 'EMP001',
                'phone': '+56912345678',
                'shift_start': '09:00',
                'shift_end': '18:00',
            },
            {
                'first_name': 'María',
                'last_name': 'González',
                'username': 'maria.garzon',
                'email': 'maria@pizzerialuigi.com',
                'employee_id': 'EMP002',
                'phone': '+56912345679',
                'shift_start': '14:00',
                'shift_end': '23:00',
            },
            {
                'first_name': 'Diego',
                'last_name': 'Silva',
                'username': 'diego.garzon',
                'email': 'diego@pizzerialuigi.com',
                'employee_id': 'EMP003',
                'phone': '+56912345680',
                'shift_start': '18:00',
                'shift_end': '02:00',
            }
        ]
        
        created_waiters = []
        
        for waiter_data in waiters_data:
            # Crear usuario si no existe
            user, created = User.objects.get_or_create(
                username=waiter_data['username'],
                defaults={
                    'first_name': waiter_data['first_name'],
                    'last_name': waiter_data['last_name'],
                    'email': waiter_data['email'],
                }
            )
            
            if created:
                user.set_password('garzon123')  # Contraseña por defecto
                user.save()
                print(f"✅ Usuario creado: {user.username}")
            else:
                print(f"👤 Usuario existente: {user.username}")
            
            # Crear perfil de garzón si no existe
            waiter, created = Waiter.objects.get_or_create(
                restaurant=restaurant,
                user=user,
                defaults={
                    'employee_id': waiter_data['employee_id'],
                    'phone': waiter_data['phone'],
                    'status': 'active',
                    'is_available': True,
                    'shift_start': waiter_data['shift_start'],
                    'shift_end': waiter_data['shift_end'],
                }
            )
            
            if created:
                print(f"🧑‍💼 Garzón creado: {waiter.full_name}")
                created_waiters.append(waiter)
            else:
                print(f"🧑‍💼 Garzón existente: {waiter.full_name}")
        
        # Asignar mesas a garzones
        assign_tables_to_waiters(restaurant, created_waiters)
        
        print(f"\n🎉 Datos de garzones creados exitosamente!")
        print(f"📍 Restaurante: {restaurant.name}")
        print(f"👥 Total de garzones: {restaurant.waiters.count()}")
        
        # Mostrar resumen
        print("\n📋 RESUMEN DE GARZONES:")
        for waiter in restaurant.waiters.all():
            assigned_tables = waiter.assigned_tables.all()
            tables_str = ', '.join([f"Mesa {t.number}" for t in assigned_tables]) if assigned_tables else "Sin mesas asignadas"
            print(f"  • {waiter.full_name} ({waiter.status}) - {tables_str}")
        
    except Restaurant.DoesNotExist:
        print("❌ Error: Restaurante 'pizzeria-luigi' no encontrado")
        print("   Asegúrate de haber ejecutado create_restaurant_data.py primero")
    except Exception as e:
        print(f"❌ Error: {e}")


def assign_tables_to_waiters(restaurant, waiters):
    """
    Asignar mesas a los garzones
    """
    tables = restaurant.tables.filter(is_active=True).order_by('number')
    
    if not tables.exists():
        print("⚠️  No hay mesas activas para asignar")
        return
    
    if not waiters:
        waiters = list(restaurant.waiters.filter(status='active'))
    
    if not waiters:
        print("⚠️  No hay garzones activos para asignar mesas")
        return
    
    print(f"\n🏷️  Asignando {tables.count()} mesas a {len(waiters)} garzones...")
    
    # Distribuir mesas equitativamente
    tables_per_waiter = tables.count() // len(waiters)
    remaining_tables = tables.count() % len(waiters)
    
    table_index = 0
    
    for i, waiter in enumerate(waiters):
        # Calcular cuántas mesas asignar a este garzón
        tables_to_assign = tables_per_waiter
        if i < remaining_tables:
            tables_to_assign += 1
        
        # Asignar mesas
        for j in range(tables_to_assign):
            if table_index < tables.count():
                table = tables[table_index]
                table.assigned_waiter = waiter
                table.save()
                print(f"   Mesa {table.number} → {waiter.full_name}")
                table_index += 1


if __name__ == '__main__':
    create_sample_waiters() 