#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GarzonGoQR.settings')
django.setup()

from restaurants.models import Tenant, Restaurant

print("🔍 DIAGNÓSTICO DE RESTAURANTES")
print("=" * 50)

# 1. Todos los tenants
print("\n📊 TODOS LOS TENANTS:")
tenants = Tenant.objects.all()
for tenant in tenants:
    print(f"   • {tenant.name} (slug: {tenant.slug}) - Status: {tenant.status}")

# 2. Todos los restaurantes
print("\n🏪 TODOS LOS RESTAURANTES:")
restaurants = Restaurant.objects.all()
for restaurant in restaurants:
    print(f"   • {restaurant.name} - Active: {restaurant.is_active} - Tenant: {restaurant.tenant.name} ({restaurant.tenant.status})")

# 3. Filtro que usa landing_view
print("\n🎯 FILTRO DE LANDING VIEW:")
filtered_restaurants = Restaurant.objects.filter(
    is_active=True,
    tenant__status='ACTIVE'
).select_related('tenant')

print(f"Total filtrados: {filtered_restaurants.count()}")
for restaurant in filtered_restaurants:
    print(f"   ✅ {restaurant.name} - {restaurant.tenant.slug}")

# 4. Problemas potenciales
print("\n⚠️  POSIBLES PROBLEMAS:")

inactive_restaurants = Restaurant.objects.filter(is_active=False)
if inactive_restaurants.exists():
    print("   • Restaurantes inactivos:")
    for rest in inactive_restaurants:
        print(f"     - {rest.name} (is_active=False)")

inactive_tenants = Tenant.objects.exclude(status='ACTIVE')
if inactive_tenants.exists():
    print("   • Tenants con status diferente a ACTIVE:")
    for tenant in inactive_tenants:
        print(f"     - {tenant.name} (status={tenant.status})")

print("\n✅ Diagnóstico completado!") 