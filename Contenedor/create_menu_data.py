#!/usr/bin/env python3
"""
Script para crear datos de prueba del menú para GarzonGoQR
Ejecutar: python create_menu_data.py
"""

import os
import sys
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GarzonGoQR.settings')
django.setup()

from restaurants.models import Tenant
from menu.models import MenuCategory, MenuItem, MenuVariant, MenuAddon, MenuModifier


def create_menu_data():
    """Crear datos de prueba para el menú"""
    
    # Obtener el tenant de Pizzería Luigi
    try:
        tenant = Tenant.objects.get(slug='pizzeria-luigi')
        print(f"✅ Usando tenant: {tenant.name}")
    except Tenant.DoesNotExist:
        print("❌ No se encontró el tenant 'pizzeria-luigi'. Ejecuta primero create_test_data.py")
        return

    # Limpiar datos existentes del menú
    print("🧹 Limpiando datos existentes del menú...")
    MenuCategory.objects.filter(tenant=tenant).delete()
    
    # === CATEGORÍAS ===
    print("📂 Creando categorías...")
    
    categories_data = [
        {
            'name': 'Entradas',
            'description': 'Deliciosas entradas para comenzar tu comida',
            'order': 1,
        },
        {
            'name': 'Pizzas',
            'description': 'Nuestras famosas pizzas artesanales con masa madre',
            'order': 2,
        },
        {
            'name': 'Pastas',
            'description': 'Pastas frescas hechas en casa todos los días',
            'order': 3,
        },
        {
            'name': 'Postres',
            'description': 'El final perfecto para tu comida',
            'order': 4,
        },
        {
            'name': 'Bebidas',
            'description': 'Refrescantes bebidas para acompañar tu comida',
            'order': 5,
        },
    ]
    
    categories = {}
    for cat_data in categories_data:
        category = MenuCategory.objects.create(
            tenant=tenant,
            **cat_data
        )
        categories[cat_data['name']] = category
        print(f"  ✅ {category.name}")

    # === PRODUCTOS ===
    print("\n🍽️ Creando productos del menú...")
    
    # ENTRADAS
    entradas_data = [
        {
            'name': 'Bruschetta Italiana',
            'description': 'Pan tostado con tomate fresco, albahaca, ajo y aceite de oliva extra virgen',
            'base_price': Decimal('8.50'),
            'is_vegetarian': True,
            'preparation_time': 10,
            'calories': 180,
        },
        {
            'name': 'Antipasto Luigi',
            'description': 'Selección de quesos, jamón serrano, aceitunas, tomates secos y focaccia',
            'base_price': Decimal('15.90'),
            'preparation_time': 5,
            'calories': 420,
            'is_featured': True,
        },
    ]
    
    for item_data in entradas_data:
        item = MenuItem.objects.create(
            tenant=tenant,
            category=categories['Entradas'],
            **item_data
        )
        print(f"  ✅ {item.name} - ${item.base_price}")

    # PIZZAS
    pizzas_data = [
        {
            'name': 'Pizza Margherita',
            'description': 'La clásica pizza italiana con salsa de tomate, mozzarella fresca y albahaca',
            'base_price': Decimal('18.90'),
            'is_vegetarian': True,
            'preparation_time': 20,
            'calories': 720,
            'is_featured': True,
        },
        {
            'name': 'Pizza Pepperoni',
            'description': 'Pizza con pepperoni premium, mozzarella y salsa de tomate especial',
            'base_price': Decimal('21.90'),
            'preparation_time': 20,
            'calories': 850,
            'is_featured': True,
        },
        {
            'name': 'Pizza Picante Luigi',
            'description': 'Salsa picante, pepperoni, chorizo, jalapeños y queso extra',
            'base_price': Decimal('26.90'),
            'discounted_price': Decimal('22.90'),  # 15% descuento
            'is_spicy': True,
            'preparation_time': 23,
            'calories': 980,
            'is_featured': True,
        },
    ]
    
    for item_data in pizzas_data:
        item = MenuItem.objects.create(
            tenant=tenant,
            category=categories['Pizzas'],
            **item_data
        )
        print(f"  ✅ {item.name} - ${item.current_price}")

    # PASTAS
    pastas_data = [
        {
            'name': 'Spaghetti Carbonara',
            'description': 'Pasta con panceta, huevo, queso parmesano y pimienta negra recién molida',
            'base_price': Decimal('16.90'),
            'preparation_time': 18,
            'calories': 650,
        },
        {
            'name': 'Lasagna de la Casa',
            'description': 'Lasagna tradicional con carne, bechamel, queso y salsa de tomate casera',
            'base_price': Decimal('19.90'),
            'preparation_time': 25,
            'calories': 750,
            'is_featured': True,
        },
    ]
    
    for item_data in pastas_data:
        item = MenuItem.objects.create(
            tenant=tenant,
            category=categories['Pastas'],
            **item_data
        )
        print(f"  ✅ {item.name} - ${item.base_price}")

    # POSTRES
    postres_data = [
        {
            'name': 'Tiramisu',
            'description': 'El clásico postre italiano con café, mascarpone y cacao',
            'base_price': Decimal('8.90'),
            'is_vegetarian': True,
            'preparation_time': 5,
            'calories': 420,
            'is_featured': True,
        },
    ]
    
    for item_data in postres_data:
        item = MenuItem.objects.create(
            tenant=tenant,
            category=categories['Postres'],
            **item_data
        )
        print(f"  ✅ {item.name} - ${item.base_price}")

    # BEBIDAS
    bebidas_data = [
        {
            'name': 'Limonada Artesanal',
            'description': 'Limonada fresca con hierbas aromáticas y agua mineral',
            'base_price': Decimal('6.90'),
            'preparation_time': 5,
            'calories': 120,
        },
        {
            'name': 'Café Espresso',
            'description': 'Auténtico café espresso italiano',
            'base_price': Decimal('3.50'),
            'preparation_time': 3,
            'calories': 5,
        },
    ]
    
    for item_data in bebidas_data:
        item = MenuItem.objects.create(
            tenant=tenant,
            category=categories['Bebidas'],
            **item_data
        )
        print(f"  ✅ {item.name} - ${item.base_price}")

    print(f"\n🎉 ¡Menú completo creado para {tenant.name}!")
    print(f"🌐 Visita: http://localhost:8000/{tenant.slug}/menu/")


if __name__ == '__main__':
    create_menu_data() 