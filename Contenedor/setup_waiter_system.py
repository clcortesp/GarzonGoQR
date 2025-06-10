#!/usr/bin/env python
"""
Script para configurar el sistema completo de garzones
"""
import os
import sys
import django
import subprocess

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GarzonGoQR.settings')
django.setup()

def run_command(command, description):
    """Ejecutar comando y mostrar resultado"""
    print(f"\n🔧 {description}")
    print(f"💻 Ejecutando: {command}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} - EXITOSO")
            if result.stdout:
                print(f"📤 Output: {result.stdout}")
        else:
            print(f"❌ {description} - ERROR")
            if result.stderr:
                print(f"🚨 Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error ejecutando comando: {e}")
        return False
    
    return True

def main():
    """Configurar sistema completo"""
    print("🚀 CONFIGURANDO SISTEMA DE GARZONES PARA GARZONGOQR")
    print("=" * 60)
    
    # 1. Crear migraciones
    success = run_command(
        "python manage.py makemigrations restaurants",
        "Creando migraciones para restaurants"
    )
    
    if success:
        success = run_command(
            "python manage.py makemigrations orders",
            "Creando migraciones para orders"
        )
    
    # 2. Aplicar migraciones
    if success:
        success = run_command(
            "python manage.py migrate",
            "Aplicando migraciones a la base de datos"
        )
    
    # 3. Crear datos de ejemplo
    if success:
        print("\n🎭 Creando datos de ejemplo...")
        try:
            # Importar y ejecutar el script de garzones
            from create_waiter_data import create_sample_waiters
            create_sample_waiters()
            print("✅ Datos de garzones creados exitosamente")
        except Exception as e:
            print(f"❌ Error creando datos de garzones: {e}")
    
    # 4. Mostrar resumen
    print("\n" + "=" * 60)
    print("📋 RESUMEN DE LA CONFIGURACIÓN")
    print("=" * 60)
    
    if success:
        print("✅ Sistema de garzones configurado exitosamente!")
        print("\n🔗 URLs DISPONIBLES:")
        print("   • Dashboard Admin: /pizzeria-luigi/admin/")
        print("   • Gestión Menú: /pizzeria-luigi/admin/menu/")
        print("   • Gestión Garzones: /pizzeria-luigi/admin/waiters/")
        print("   • Gestión Mesas: /pizzeria-luigi/admin/tables/")
        print("   • Reportes Ventas: /pizzeria-luigi/admin/reports/sales/")
        print("   • Dashboard Garzón: /pizzeria-luigi/waiter/")
        
        print("\n👤 USUARIOS DE PRUEBA:")
        print("   • Garzones: carlos.garzon, maria.garzon, diego.garzon")
        print("   • Contraseña: garzon123")
        
        print("\n🏃‍♂️ SIGUIENTE PASO:")
        print("   python manage.py runserver")
        print("   Luego ve a: http://localhost:8000/pizzeria-luigi/admin/")
        
    else:
        print("❌ Hubo errores en la configuración")
        print("💡 Revisa los mensajes de error arriba")

if __name__ == '__main__':
    main() 