#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Contenedor.settings')
django.setup()

from django.contrib.auth.models import User
from tenant_app.models import Tenant
from restaurants.models import Restaurant, Waiter, Table

def check_and_create_waiters():
    """Verificar y crear garzones de prueba si no existen"""
    
    print("=== VERIFICACIÓN DE GARZONES ===")
    
    # Obtener el primer tenant/restaurante disponible
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ No hay tenants en el sistema")
        return
    
    restaurant = Restaurant.objects.filter(tenant=tenant).first()
    if not restaurant:
        print("❌ No hay restaurantes en el sistema")
        return
    
    print(f"🏢 Restaurante: {restaurant.name}")
    print(f"🏪 Tenant: {tenant.name} ({tenant.slug})")
    
    # Verificar garzones existentes
    waiters = Waiter.objects.filter(restaurant=restaurant)
    print(f"👥 Garzones existentes: {waiters.count()}")
    
    if waiters.exists():
        for waiter in waiters:
            print(f"  - {waiter.full_name} ({waiter.user.username})")
    else:
        print("📝 No hay garzones. Creando garzones de prueba...")
        
        # Crear usuarios y garzones de prueba
        waiter_data = [
            {
                'username': 'garzon1',
                'first_name': 'Carlos',
                'last_name': 'Pérez',
                'email': 'carlos@ejemplo.com',
                'shift': 'morning'
            },
            {
                'username': 'garzon2', 
                'first_name': 'María',
                'last_name': 'González',
                'email': 'maria@ejemplo.com',
                'shift': 'afternoon'
            },
            {
                'username': 'garzon3',
                'first_name': 'Juan',
                'last_name': 'López',
                'email': 'juan@ejemplo.com', 
                'shift': 'evening'
            }
        ]
        
        created_waiters = []
        
        for data in waiter_data:
            # Crear o obtener usuario
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'email': data['email'],
                    'is_active': True
                }
            )
            
            if created:
                user.set_password('123456')  # Contraseña simple para pruebas
                user.save()
                print(f"✅ Usuario creado: {user.username}")
            else:
                print(f"🔄 Usuario ya existe: {user.username}")
            
            # Crear garzón
            waiter, created = Waiter.objects.get_or_create(
                restaurant=restaurant,
                user=user,
                defaults={
                    'phone': f'+56912345{len(created_waiters)+1:03d}',
                    'shift': data['shift'],
                    'status': 'active',
                    'is_available': True
                }
            )
            
            if created:
                print(f"✅ Garzón creado: {waiter.full_name}")
                created_waiters.append(waiter)
            else:
                print(f"🔄 Garzón ya existe: {waiter.full_name}")
        
        # Asignar mesas si existen
        tables = Table.objects.filter(restaurant=restaurant)
        if tables.exists() and created_waiters:
            print(f"🍽️ Asignando {tables.count()} mesas a los garzones...")
            
            for i, table in enumerate(tables):
                waiter = created_waiters[i % len(created_waiters)]  # Rotar entre garzones
                table.assigned_waiter = waiter
                table.save()
                print(f"  Mesa {table.number} → {waiter.full_name}")
        
        print(f"✅ {len(created_waiters)} garzones creados y configurados")
    
    print("\n=== RESUMEN ===")
    print(f"👥 Total garzones: {Waiter.objects.filter(restaurant=restaurant).count()}")
    print(f"🍽️ Total mesas: {Table.objects.filter(restaurant=restaurant).count()}")
    print(f"🔗 Mesas asignadas: {Table.objects.filter(restaurant=restaurant, assigned_waiter__isnull=False).count()}")
    
    print("\n=== CREDENCIALES DE PRUEBA ===")
    for waiter in Waiter.objects.filter(restaurant=restaurant):
        print(f"👤 Usuario: {waiter.user.username} | Contraseña: 123456 | Garzón: {waiter.full_name}")
    
    print(f"\n🌐 Accede como garzón en: http://localhost:8000/{tenant.slug}/")

if __name__ == '__main__':
    check_and_create_waiters() 