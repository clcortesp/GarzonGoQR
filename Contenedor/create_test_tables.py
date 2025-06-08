#!/usr/bin/env python3
"""
Script para crear mesas de prueba para el sistema QR
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Contenedor.settings')
django.setup()

from restaurants.models import Restaurant, Tenant, Table

def create_test_tables():
    """Crear mesas de prueba para Pizzería Luigi"""
    print("🍕 Creando mesas de prueba para Pizzería Luigi...")
    
    try:
        # Obtener el restaurante
        tenant = Tenant.objects.get(slug='pizzeria-luigi')
        restaurant = tenant.restaurant
        print(f"✅ Restaurant encontrado: {restaurant.name}")
        
        # Definir mesas de prueba
        test_tables = [
            {'number': '1', 'name': 'Mesa Principal 1', 'capacity': 4, 'location': 'Salón Principal'},
            {'number': '2', 'name': 'Mesa Principal 2', 'capacity': 4, 'location': 'Salón Principal'},
            {'number': '3', 'name': 'Mesa Principal 3', 'capacity': 6, 'location': 'Salón Principal'},
            {'number': '4', 'name': 'Mesa Principal 4', 'capacity': 2, 'location': 'Salón Principal'},
            {'number': '5', 'name': 'Mesa Principal 5', 'capacity': 4, 'location': 'Salón Principal'},
            
            {'number': 'T1', 'name': 'Mesa Terraza 1', 'capacity': 4, 'location': 'Terraza'},
            {'number': 'T2', 'name': 'Mesa Terraza 2', 'capacity': 6, 'location': 'Terraza'},
            {'number': 'T3', 'name': 'Mesa Terraza 3', 'capacity': 2, 'location': 'Terraza'},
            
            {'number': 'VIP1', 'name': 'Mesa VIP 1', 'capacity': 8, 'location': 'Área VIP'},
            {'number': 'VIP2', 'name': 'Mesa VIP 2', 'capacity': 10, 'location': 'Área VIP'},
            
            {'number': 'B1', 'name': 'Mesa Bar 1', 'capacity': 2, 'location': 'Barra'},
            {'number': 'B2', 'name': 'Mesa Bar 2', 'capacity': 2, 'location': 'Barra'},
        ]
        
        created_count = 0
        
        for table_data in test_tables:
            # Verificar si ya existe
            if Table.objects.filter(restaurant=restaurant, number=table_data['number']).exists():
                print(f"⚠️  Mesa {table_data['number']} ya existe, saltando...")
                continue
            
            # Crear mesa
            table = Table.objects.create(
                restaurant=restaurant,
                number=table_data['number'],
                name=table_data['name'],
                capacity=table_data['capacity'],
                location=table_data['location'],
                is_active=True,
                qr_enabled=True
            )
            
            print(f"✅ Mesa creada: {table.display_name} (Capacidad: {table.capacity})")
            print(f"   📱 QR URL: {table.full_qr_url}")
            print(f"   🆔 UUID: {table.qr_code_uuid}")
            print()
            
            created_count += 1
        
        print(f"🎉 ¡Proceso completado!")
        print(f"📊 Mesas creadas: {created_count}")
        print(f"📊 Total de mesas: {Table.objects.filter(restaurant=restaurant).count()}")
        
        # Mostrar URLs de ejemplo
        print("\n🔗 URLs de ejemplo para probar:")
        sample_tables = Table.objects.filter(restaurant=restaurant)[:3]
        for table in sample_tables:
            print(f"   Mesa {table.number}: {table.full_qr_url}")
        
        print(f"\n🎯 Panel de gestión: http://localhost:8000/{tenant.slug}/tables/")
        
    except Tenant.DoesNotExist:
        print("❌ Error: No se encontró el tenant 'pizzeria-luigi'")
        print("   Ejecuta primero: python create_restaurant_data.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    create_test_tables() 