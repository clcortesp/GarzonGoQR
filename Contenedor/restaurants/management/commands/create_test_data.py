from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from restaurants.models import Tenant, Restaurant
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Crear datos de prueba para el sistema multi-tenant'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenants',
            type=int,
            default=3,
            help='Número de tenants a crear (default: 3)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpiar datos existentes antes de crear nuevos'
        )
    
    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('🗑️  Limpiando datos existentes...'))
            Restaurant.objects.all().delete()
            Tenant.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
        
        num_tenants = options['tenants']
        self.stdout.write(f'🚀 Creando {num_tenants} tenants de prueba...')
        
        # Datos de ejemplo
        restaurant_data = [
            {
                'name': 'Pizzería Luigi',
                'slug': 'pizzeria-luigi',
                'address': 'Calle de la Pizza 15, Madrid',
                'phone': '+34 91 123 4567',
                'email': 'contacto@pizzerialuigi.com',
                'color': '#e74c3c',
                'owner_data': {
                    'username': 'luigi_owner',
                    'email': 'luigi@pizzerialuigi.com',
                    'first_name': 'Luigi',
                    'last_name': 'Rossi'
                }
            },
            {
                'name': 'Restaurante Marisquería El Mar',
                'slug': 'marisqueria-el-mar',
                'address': 'Puerto Pesquero 8, Valencia',
                'phone': '+34 96 987 6543',
                'email': 'info@marisqueriaelmar.es',
                'color': '#3498db',
                'owner_data': {
                    'username': 'mar_owner',
                    'email': 'carlos@marisqueriaelmar.es',
                    'first_name': 'Carlos',
                    'last_name': 'Martínez'
                }
            },
            {
                'name': 'Tapas Bar Andaluz',
                'slug': 'tapas-bar-andaluz',
                'address': 'Plaza Mayor 12, Sevilla',
                'phone': '+34 95 456 7890',
                'email': 'hola@tapasbarandaluz.com',
                'color': '#f39c12',
                'owner_data': {
                    'username': 'andaluz_owner',
                    'email': 'maria@tapasbarandaluz.com',
                    'first_name': 'María',
                    'last_name': 'García'
                }
            },
            {
                'name': 'Burger House',
                'slug': 'burger-house',
                'address': 'Avenida Gran Vía 45, Barcelona',
                'phone': '+34 93 234 5678',
                'email': 'pedidos@burgerhouse.es',
                'color': '#9b59b6',
                'owner_data': {
                    'username': 'burger_owner',
                    'email': 'david@burgerhouse.es',
                    'first_name': 'David',
                    'last_name': 'López'
                }
            },
            {
                'name': 'Sushi Zen',
                'slug': 'sushi-zen',
                'address': 'Calle Serrano 89, Madrid',
                'phone': '+34 91 345 6789',
                'email': 'reservas@sushizen.es',
                'color': '#2ecc71',
                'owner_data': {
                    'username': 'zen_owner',
                    'email': 'kenji@sushizen.es',
                    'first_name': 'Kenji',
                    'last_name': 'Tanaka'
                }
            }
        ]
        
        created_count = 0
        
        for i in range(min(num_tenants, len(restaurant_data))):
            data = restaurant_data[i]
            
            try:
                # Crear usuario propietario
                owner = User.objects.create_user(
                    username=data['owner_data']['username'],
                    email=data['owner_data']['email'],
                    password='demo123',  # Contraseña simple para testing
                    first_name=data['owner_data']['first_name'],
                    last_name=data['owner_data']['last_name']
                )
                
                # Crear tenant
                status = random.choice(['ACTIVE', 'TRIAL', 'ACTIVE', 'ACTIVE'])  # Más activos
                plan = random.choice(['BASIC', 'PROFESSIONAL', 'BASIC'])
                
                tenant = Tenant.objects.create(
                    name=data['name'],
                    slug=data['slug'],
                    status=status,
                    subscription_plan=plan,
                    primary_color=data['color'],
                    trial_ends_at=datetime.now() + timedelta(days=30) if status == 'TRIAL' else None
                )
                
                # Crear restaurant
                restaurant = Restaurant.objects.create(
                    tenant=tenant,
                    name=data['name'],
                    address=data['address'],
                    phone=data['phone'],
                    email=data['email'],
                    owner=owner,
                    is_active=True,
                    opening_time='09:00',
                    closing_time='23:00'
                )
                
                created_count += 1
                
                # Mostrar resultado
                status_color = self.get_status_color(status)
                self.stdout.write(
                    f'✅ {status_color}{data["name"]}{self.style.RESET} '
                    f'({data["slug"]}) - {status} - {plan}'
                )
                self.stdout.write(
                    f'   👤 Owner: {owner.get_full_name()} ({owner.username})'
                )
                self.stdout.write(
                    f'   🌐 URL: http://localhost:8000/{data["slug"]}/'
                )
                self.stdout.write('')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error creando {data["name"]}: {str(e)}')
                )
        
        # Resumen final
        self.stdout.write(self.style.SUCCESS(f'🎉 ¡Creados {created_count} tenants exitosamente!'))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('📋 URLs de prueba:'))
        
        for tenant in Tenant.objects.all()[:5]:
            self.stdout.write(f'   • http://localhost:8000/{tenant.slug}/')
        
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('👤 Usuarios creados (password: demo123):'))
        
        for user in User.objects.filter(is_superuser=False):
            self.stdout.write(f'   • {user.username} ({user.email})')
        
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('🔑 Para acceso admin:'))
        self.stdout.write('   python manage.py createsuperuser')
    
    def get_status_color(self, status):
        colors = {
            'ACTIVE': self.style.SUCCESS,
            'TRIAL': self.style.WARNING,
            'SUSPENDED': self.style.ERROR,
            'EXPIRED': self.style.HTTP_NOT_MODIFIED
        }
        return colors.get(status, self.style.SUCCESS)('') 