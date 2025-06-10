# restaurants/models.py
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class Tenant(models.Model):
    """Modelo core del sistema multi-tenant"""
    
    STATUS_CHOICES = [
        ('TRIAL', 'Período de prueba'),
        ('ACTIVE', 'Activo'),
        ('SUSPENDED', 'Suspendido'),
        ('EXPIRED', 'Expirado'),
    ]
    
    PLAN_CHOICES = [
        ('BASIC', 'Básico'),
        ('PROFESSIONAL', 'Profesional'),
        ('ENTERPRISE', 'Empresarial'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Nombre del negocio")
    slug = models.SlugField(unique=True, max_length=50, 
                          help_text="URL única: tuapp.com/este-slug/")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TRIAL')
    subscription_plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='BASIC')
    
    # Configuración de dominio para QR
    domain = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="Dominio personalizado",
        help_text="ej: mirestaurante.com (opcional, para QRs personalizados)"
    )
    
    # Branding básico
    primary_color = models.CharField(max_length=7, default='#007bff', 
                                   help_text="Color primario en formato hex")
    logo = models.ImageField(upload_to='tenants/logos/', null=True, blank=True)
    
    # Fechas importantes
    created_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        
    def __str__(self):
        return f"{self.name} ({self.slug})"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Restaurant(models.Model):
    """Información del restaurante asociado al tenant"""
    
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, 
                                 related_name='restaurant')
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    
    # Propietario del restaurante
    owner = models.ForeignKey(User, on_delete=models.CASCADE, 
                            related_name='owned_restaurants')
    
    # Estado
    is_active = models.BooleanField(default=True)
    
    # Horarios básicos
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Restaurante'
        verbose_name_plural = 'Restaurantes'
        
    def __str__(self):
        return f"{self.name} - {self.tenant.slug}"

class RestaurantEmployee(models.Model):
    """
    Clase base abstracta para todos los empleados del restaurante
    """
    
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('on_break', 'En descanso'),
        ('busy', 'Ocupado'),
    ]
    
    # Relaciones básicas
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Información del empleado
    employee_id = models.CharField(max_length=20, blank=True, verbose_name="ID de empleado")
    phone = models.CharField(max_length=20, blank=True)
    
    # Estado laboral
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_available = models.BooleanField(default=True, verbose_name="Disponible para notificaciones")
    
    # Configuración de notificaciones
    notification_email = models.BooleanField(default=True, verbose_name="Recibir emails")
    notification_push = models.BooleanField(default=True, verbose_name="Notificaciones push")
    notification_sound = models.BooleanField(default=True, verbose_name="Sonido de notificación")
    
    # Horarios de trabajo (opcional)
    shift_start = models.TimeField(null=True, blank=True, verbose_name="Inicio de turno")
    shift_end = models.TimeField(null=True, blank=True, verbose_name="Fin de turno")
    
    # Estadísticas básicas
    total_tasks_completed = models.PositiveIntegerField(default=0)
    average_completion_time = models.PositiveIntegerField(default=0, help_text="En minutos")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
    
    @property
    def full_name(self):
        """Nombre completo del empleado"""
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    @property
    def is_working_hours(self):
        """Verificar si está en horario de trabajo"""
        if not self.shift_start or not self.shift_end:
            return True  # Sin horario definido = siempre disponible
        
        from django.utils import timezone
        now = timezone.now().time()
        return self.shift_start <= now <= self.shift_end
    
    def update_activity(self):
        """Actualizar última actividad"""
        from django.utils import timezone
        self.last_active = timezone.now()
        self.save(update_fields=['last_active'])

class KitchenStaff(RestaurantEmployee):
    """
    Personal de cocina - se encarga de preparar los alimentos
    """
    
    PRIORITY_CHOICES = [
        ('low', 'Baja - Cocinero Jr.'),
        ('medium', 'Media - Cocinero Sr.'),
        ('high', 'Alta - Chef'),
    ]
    
    # Especialidades (opcional)
    specialties = models.JSONField(
        default=list, 
        blank=True,
        help_text="Lista de especialidades: ['pasta', 'pizza', 'carnes']"
    )
    
    # Configuración específica de cocina
    can_modify_prep_time = models.BooleanField(default=False, verbose_name="Puede modificar tiempo de preparación")
    priority_level = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Nivel de prioridad")
    years_experience = models.PositiveIntegerField(default=0, verbose_name="Años de experiencia")
    
    # Estadísticas específicas de cocina
    total_dishes_prepared = models.PositiveIntegerField(default=0)
    average_prep_time = models.PositiveIntegerField(default=15, help_text="Tiempo promedio en minutos")
    
    class Meta:
        verbose_name = 'Personal de Cocina'
        verbose_name_plural = 'Personal de Cocina'
        unique_together = ['restaurant', 'user']
        ordering = ['-priority_level', 'user__first_name']
    
    def __str__(self):
        return f"Cocina: {self.full_name} - {self.restaurant.name}"
    
    @property
    def role_display(self):
        """Mostrar rol según prioridad"""
        roles = {1: 'Cocinero Jr.', 2: 'Cocinero Sr.', 3: 'Chef'}
        return roles.get(self.priority_level, 'Cocinero')

class BarStaff(RestaurantEmployee):
    """
    Personal de bar - se encarga de preparar bebidas
    """
    
    # Tipos de bebidas que puede preparar
    DRINK_TYPES = [
        ('alcoholic', 'Bebidas alcohólicas'),
        ('non_alcoholic', 'Bebidas sin alcohol'), 
        ('coffee', 'Café y bebidas calientes'),
        ('cocktails', 'Cócteles'),
        ('all', 'Todas las bebidas'),
    ]
    
    drink_specialties = models.JSONField(
        default=list,
        blank=True, 
        help_text="Tipos de bebidas que puede preparar"
    )
    
    # Certificaciones como JSONField
    certifications = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de certificaciones: ['bartender', 'sommelier']"
    )
    
    # Certificaciones (opcional)
    has_bartender_license = models.BooleanField(default=False, verbose_name="Licencia de barman")
    can_serve_alcohol = models.BooleanField(default=True, verbose_name="Puede servir alcohol")
    years_experience = models.PositiveIntegerField(default=0, verbose_name="Años de experiencia")
    
    # Estadísticas específicas de bar
    total_drinks_prepared = models.PositiveIntegerField(default=0)
    average_prep_time = models.PositiveIntegerField(default=5, help_text="Tiempo promedio en minutos")
    
    class Meta:
        verbose_name = 'Personal de Bar'
        verbose_name_plural = 'Personal de Bar'
        unique_together = ['restaurant', 'user']
        ordering = ['user__first_name']
    
    def __str__(self):
        return f"Bar: {self.full_name} - {self.restaurant.name}"
    
    @property
    def role_display(self):
        """Mostrar rol"""
        if self.has_bartender_license:
            return 'Barman Certificado'
        return 'Preparador de Bebidas'

# Mantener el modelo Waiter existente pero heredando de RestaurantEmployee
class WaiterStaff(RestaurantEmployee):
    """
    Personal de servicio - se encarga de servir pedidos y atender mesas
    """
    
    # Estadísticas específicas de servicio
    total_orders_served = models.PositiveIntegerField(default=0)
    average_response_time = models.PositiveIntegerField(default=0, help_text="En minutos")
    rating_average = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    years_experience = models.PositiveIntegerField(default=0, verbose_name="Años de experiencia")
    tips_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Porcentaje de propinas")
    
    # Configuración específica de garzón
    can_take_orders = models.BooleanField(default=True, verbose_name="Puede tomar pedidos manualmente")
    max_tables_assigned = models.PositiveIntegerField(default=6, verbose_name="Máximo de mesas asignadas")
    
    class Meta:
        verbose_name = 'Garzón'
        verbose_name_plural = 'Garzones'
        unique_together = ['restaurant', 'user']
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"Garzón: {self.full_name} - {self.restaurant.name}"
    
    @property
    def assigned_tables_count(self):
        """Número de mesas asignadas"""
        return self.assigned_tables.filter(is_active=True).count()
    
    @property
    def role_display(self):
        return 'Garzón de Servicio'


# Mantener modelo Waiter original para compatibilidad
class Waiter(RestaurantEmployee):
    """
    Modelo original de garzones - mantener para compatibilidad con sistema existente
    """
    
    # Estadísticas específicas (igual que WaiterStaff)
    total_orders_served = models.PositiveIntegerField(default=0)
    average_response_time = models.PositiveIntegerField(default=0, help_text="En minutos")
    rating_average = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    class Meta:
        verbose_name = 'Garzón'
        verbose_name_plural = 'Garzones'
        unique_together = ['restaurant', 'user']
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.restaurant.name}"
    
    @property
    def assigned_tables_count(self):
        return self.assigned_tables.filter(is_active=True).count()


class Table(models.Model):
    """
    Modelo para las mesas del restaurante
    """
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='tables')
    number = models.CharField(max_length=10, verbose_name="Número de mesa")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre descriptivo")
    capacity = models.PositiveIntegerField(default=4, verbose_name="Capacidad (personas)")
    
    # Asignación de garzón (mantener compatibilidad)
    assigned_waiter = models.ForeignKey(
        'Waiter', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_tables',
        verbose_name="Garzón asignado"
    )
    
    # QR Code
    qr_code_uuid = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="UUID para QR")
    qr_enabled = models.BooleanField(default=True, verbose_name="QR habilitado")
    
    # Ubicación y estado
    location = models.CharField(max_length=100, blank=True, verbose_name="Ubicación (ej: terraza, interior)")
    is_active = models.BooleanField(default=True, verbose_name="Mesa activa")
    
    # Estadísticas
    total_scans = models.PositiveIntegerField(default=0, verbose_name="Total de escaneos")
    last_scan = models.DateTimeField(null=True, blank=True, verbose_name="Último escaneo")
    total_orders = models.PositiveIntegerField(default=0, verbose_name="Total de pedidos")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"
        unique_together = ['restaurant', 'number']
        ordering = ['number']
    
    def __str__(self):
        return f"Mesa {self.number} - {self.restaurant.name}"
    
    @property
    def display_name(self):
        """Nombre para mostrar"""
        return self.name if self.name else f"Mesa {self.number}"
    
    @property
    def qr_url(self):
        """URL que genera el código QR"""
        return f"/{self.restaurant.tenant.slug}/table/{self.qr_code_uuid}/"
    
    @property
    def full_qr_url(self):
        """URL completa para el QR code"""
        return self.get_full_qr_url()
    
    def get_full_qr_url(self, request=None):
        """
        Obtener URL completa del QR con diferentes estrategias
        """
        from django.conf import settings
        
        # 1. Si hay request disponible, usar build_absolute_uri (MEJOR)
        if request:
            return request.build_absolute_uri(self.qr_url)
        
        # 2. Si el tenant tiene dominio configurado
        if hasattr(self.restaurant.tenant, 'domain') and self.restaurant.tenant.domain:
            protocol = 'https' if getattr(settings, 'USE_HTTPS', False) else 'http'
            return f"{protocol}://{self.restaurant.tenant.domain}{self.qr_url}"
        
        # 3. Usar configuración en settings
        base_url = getattr(settings, 'QR_BASE_URL', None)
        if base_url:
            return f"{base_url.rstrip('/')}{self.qr_url}"
        
        # 4. Fallback por defecto para desarrollo
        default_base = getattr(settings, 'DEBUG', False) and "http://localhost:8000" or "https://midominio.com"
        return f"{default_base}{self.qr_url}"
    
    def increment_scan_count(self):
        """Incrementar contador de escaneos"""
        from django.utils import timezone
        self.total_scans += 1
        self.last_scan = timezone.now()
        self.save(update_fields=['total_scans', 'last_scan'])
    
    def increment_order_count(self):
        """Incrementar contador de pedidos"""
        self.total_orders += 1
        self.save(update_fields=['total_orders'])

class WaiterNotification(models.Model):
    """
    Sistema de notificaciones para garzones
    """
    
    NOTIFICATION_TYPES = [
        ('new_order', 'Nuevo pedido'),
        ('order_ready', 'Pedido listo'),
        ('customer_request', 'Solicitud del cliente'),
        ('table_call', 'Llamada de mesa'),
        ('urgent', 'Urgente'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('read', 'Leído'),
        ('responded', 'Respondido'),
        ('dismissed', 'Descartado'),
    ]
    
    # Relaciones
    waiter = models.ForeignKey('Waiter', on_delete=models.CASCADE, related_name='notifications')
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='notifications')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, null=True, blank=True)
    
    # Contenido de la notificación
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.PositiveIntegerField(default=1, help_text="1=Normal, 2=Alta, 3=Urgente")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Metadatos
    metadata = models.JSONField(default=dict, blank=True, help_text="Datos adicionales")
    
    class Meta:
        verbose_name = 'Notificación de Garzón'
        verbose_name_plural = 'Notificaciones de Garzones'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['waiter', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.waiter.full_name} - Mesa {self.table.number}"
    
    def mark_as_read(self):
        """Marcar como leído"""
        if self.status == 'pending':
            from django.utils import timezone
            self.status = 'read'
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])
    
    def mark_as_responded(self):
        """Marcar como respondido"""
        from django.utils import timezone
        self.status = 'responded'
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'responded_at'])

class TableScanLog(models.Model):
    """
    Registro de escaneos de códigos QR de mesas
    """
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='scan_logs')
    scanned_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Información del resultado
    resulted_in_order = models.BooleanField(default=False, verbose_name="Resultó en pedido")
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Registro de escaneo QR"
        verbose_name_plural = "Registros de escaneos QR"
        ordering = ['-scanned_at']
    
    def __str__(self):
        return f"Escaneo {self.table} - {self.scanned_at.strftime('%Y-%m-%d %H:%M')}"

