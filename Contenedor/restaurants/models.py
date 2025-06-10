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

class Waiter(models.Model):
    """
    Modelo para los garzones/meseros del restaurante
    """
    
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('on_break', 'En descanso'),
        ('busy', 'Ocupado'),
    ]
    
    # Relaciones básicas
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='waiters')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='waiter_profile')
    
    # Información del garzón
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
    
    # Estadísticas
    total_orders_served = models.PositiveIntegerField(default=0)
    average_response_time = models.PositiveIntegerField(default=0, help_text="En minutos")
    rating_average = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Garzón'
        verbose_name_plural = 'Garzones'
        unique_together = ['restaurant', 'user']
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.restaurant.name}"
    
    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username
    
    @property
    def assigned_tables_count(self):
        return self.assigned_tables.count()
    
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

class Table(models.Model):
    """
    Modelo para las mesas del restaurante
    """
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='tables')
    number = models.CharField(max_length=10, verbose_name="Número de mesa")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre descriptivo")
    capacity = models.PositiveIntegerField(default=4, verbose_name="Capacidad (personas)")
    
    # Asignación de garzón
    assigned_waiter = models.ForeignKey(
        Waiter, 
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
    waiter = models.ForeignKey(Waiter, on_delete=models.CASCADE, related_name='notifications')
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

