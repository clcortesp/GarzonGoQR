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

class Table(models.Model):
    """
    Modelo para las mesas del restaurante
    """
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='tables')
    number = models.CharField(max_length=10, verbose_name="Número de mesa")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre descriptivo")
    capacity = models.PositiveIntegerField(default=4, verbose_name="Capacidad (personas)")
    
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
        # En producción sería tu dominio real
        base_url = "http://localhost:8000"  # Cambiar en producción
        return f"{base_url}{self.qr_url}"
    
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

