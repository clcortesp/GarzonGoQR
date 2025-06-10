from django.core.management.base import BaseCommand
from django.db import transaction
from restaurants.models import Waiter, WaiterStaff, Table


class Command(BaseCommand):
    help = 'Migra datos del modelo Waiter al modelo WaiterStaff'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se va a migrar sin hacer cambios reales',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('MODO DRY-RUN: No se harán cambios reales')
            )
        
        try:
            # Contar waiters existentes
            waiters = Waiter.objects.all()
            waiter_count = waiters.count()
            
            if waiter_count == 0:
                self.stdout.write(
                    self.style.SUCCESS('No hay garzones en el sistema antiguo para migrar.')
                )
                return
            
            self.stdout.write(f'Encontrados {waiter_count} garzones para migrar...')
            
            migrated_count = 0
            error_count = 0
            
            with transaction.atomic():
                for waiter in waiters:
                    try:
                        # Verificar si ya existe un WaiterStaff para este usuario
                        existing_staff = WaiterStaff.objects.filter(
                            user=waiter.user,
                            restaurant=waiter.restaurant
                        ).first()
                        
                        if existing_staff:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Ya existe WaiterStaff para {waiter.user.username} - Saltando'
                                )
                            )
                            continue
                        
                        if not dry_run:
                            # Crear nuevo WaiterStaff con datos del Waiter
                            waiter_staff = WaiterStaff.objects.create(
                                user=waiter.user,
                                restaurant=waiter.restaurant,
                                employee_id=waiter.employee_id or WaiterStaff.generate_employee_id(waiter.restaurant),
                                phone=waiter.phone,
                                status=waiter.status,
                                is_available=getattr(waiter, 'is_available', True),
                                notification_email=getattr(waiter, 'notification_email', True),
                                notification_push=getattr(waiter, 'notification_push', True),
                                notification_sound=getattr(waiter, 'notification_sound', True),
                                shift_start=waiter.shift_start,
                                shift_end=waiter.shift_end,
                                total_orders_served=waiter.total_orders_served,
                                average_response_time=waiter.average_response_time,
                                rating_average=waiter.rating_average,
                                years_experience=0,  # Campo nuevo, valor por defecto
                                tips_percentage=None,  # Campo nuevo
                                can_take_orders=True,  # Campo nuevo, valor por defecto
                                max_tables_assigned=6,  # Campo nuevo, valor por defecto
                            )
                            
                            # Migrar asignaciones de mesas
                            tables = Table.objects.filter(assigned_waiter=waiter)
                            for table in tables:
                                table.assigned_waiter_staff = waiter_staff
                                table.save()
                                
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Migrado: {waiter.user.get_full_name()} ({waiter.employee_id}) '
                                    f'- {tables.count()} mesas asignadas'
                                )
                            )
                        else:
                            # Modo dry-run: solo mostrar qué se haría
                            tables_count = Table.objects.filter(assigned_waiter=waiter).count()
                            self.stdout.write(
                                f'  → Migraría: {waiter.user.get_full_name()} ({waiter.employee_id}) '
                                f'- {tables_count} mesas asignadas'
                            )
                        
                        migrated_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'✗ Error migrando {waiter.user.username}: {e}'
                            )
                        )
                
                if dry_run:
                    # En dry-run, hacer rollback
                    transaction.set_rollback(True)
            
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n🎉 Migración completada!'
                        f'\n  • {migrated_count} garzones migrados exitosamente'
                        f'\n  • {error_count} errores encontrados'
                        f'\n\nAhora puedes:'
                        f'\n  1. Verificar que los datos se migraron correctamente'
                        f'\n  2. Eliminar el modelo Waiter cuando estés seguro'
                        f'\n  3. Ejecutar: python manage.py cleanup_old_waiter_model'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n📋 Resumen del dry-run:'
                        f'\n  • {migrated_count} garzones serían migrados'
                        f'\n  • {error_count} errores potenciales'
                        f'\n\nPara ejecutar la migración real:'
                        f'\n  python manage.py migrate_waiters_to_waiterstaff'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error general durante la migración: {e}')
            ) 