from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid
from restaurants.models import Restaurant
from menu.models import MenuItem, MenuVariant, MenuAddon, MenuModifier


class Order(models.Model):
    """
    Modelo principal para los pedidos
    """
    
    # Estados del pedido
    STATUS_CHOICES = [
        ('pending', 'Pendiente de confirmación'),
        ('confirmed', 'Confirmado'),
        ('preparing', 'En preparación'),
        ('ready', 'Listo para entregar'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado'),
    ]
    
    # Tipos de pedido
    ORDER_TYPE_CHOICES = [
        ('dine_in', 'Mesa del restaurante'),
        ('takeaway', 'Para llevar'),
        ('delivery', 'Domicilio'),
    ]
    
    # Métodos de pago
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Efectivo'),
        ('card', 'Tarjeta'),
        ('transfer', 'Transferencia'),
        ('digital_wallet', 'Billetera digital'),
    ]
    
    # Identificación
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    
    # Relaciones
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='orders')
    customer_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    table = models.ForeignKey('restaurants.Table', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    
    # Información del cliente
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    
    # Detalles del pedido
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='dine_in')
    table_number = models.CharField(max_length=10, blank=True, help_text="Número de mesa (si aplica) - Deprecated: usar table")
    delivery_address = models.TextField(blank=True, help_text="Dirección de entrega (si aplica)")
    
    # Estado y timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    estimated_preparation_time = models.PositiveIntegerField(
        default=30, 
        help_text="Tiempo estimado de preparación en minutos"
    )
    
    # Precios
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Pago
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendiente'),
            ('paid', 'Pagado'),
            ('refunded', 'Reembolsado'),
        ],
        default='pending'
    )
    
    # Notas
    customer_notes = models.TextField(blank=True, help_text="Notas especiales del cliente")
    internal_notes = models.TextField(blank=True, help_text="Notas internas del restaurante")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Metadatos
    rating = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Calificación del cliente (1-5)"
    )
    review = models.TextField(blank=True, help_text="Reseña del cliente")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        indexes = [
            models.Index(fields=['restaurant', 'status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generar número de orden único
            import datetime
            date_str = datetime.datetime.now().strftime('%Y%m%d')
            last_order = Order.objects.filter(
                restaurant=self.restaurant,
                order_number__startswith=f"ORD-{date_str}"
            ).order_by('-order_number').first()
            
            if last_order:
                last_num = int(last_order.order_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.order_number = f"ORD-{date_str}-{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.order_number} - {self.customer_name} ({self.get_status_display()})"
    
    @property
    def total_items(self):
        """Número total de items en el pedido"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def can_be_cancelled(self):
        """Verificar si el pedido puede ser cancelado"""
        return self.status in ['pending', 'confirmed']
    
    @property
    def can_be_modified(self):
        """Verificar si el pedido puede ser modificado"""
        return self.status == 'pending'
    
    @property
    def estimated_ready_time(self):
        """Hora estimada de finalización"""
        if self.confirmed_at:
            from datetime import timedelta
            return self.confirmed_at + timedelta(minutes=self.estimated_preparation_time)
        return None


class OrderItem(models.Model):
    """
    Items individuales dentro de un pedido
    """
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    
    # Configuración del item
    quantity = models.PositiveIntegerField(default=1)
    
    # Variante seleccionada (tamaño, tipo, etc.)
    selected_variant = models.ForeignKey(
        MenuVariant, 
        on_delete=models.SET_NULL, 
        null=True, blank=True
    )
    
    # Addons seleccionados (extras)
    selected_addons = models.ManyToManyField(
        MenuAddon, 
        blank=True,
        help_text="Extras agregados al producto"
    )
    
    # Modificadores seleccionados (sin cebolla, etc.)
    selected_modifiers = models.ManyToManyField(
        MenuModifier,
        blank=True,
        help_text="Modificaciones al producto"
    )
    
    # Precios (guardados para histórico)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    variant_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    addons_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    modifiers_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Notas específicas del item
    special_instructions = models.TextField(blank=True, help_text="Instrucciones especiales para este item")
    
    # Estado específico del item
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendiente'),
            ('preparing', 'Preparando'),
            ('ready', 'Listo'),
            ('served', 'Servido'),
        ],
        default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Item del Pedido'
        verbose_name_plural = 'Items del Pedido'
        indexes = [
            models.Index(fields=['order', 'status']),
        ]
    
    def __str__(self):
        variant_str = f" ({self.selected_variant.name})" if self.selected_variant else ""
        return f"{self.quantity}x {self.menu_item.name}{variant_str}"
    
    @property
    def item_description(self):
        """Descripción completa del item con todas sus configuraciones"""
        desc = self.menu_item.name
        
        if self.selected_variant:
            desc += f" - {self.selected_variant.name}"
        
        addons = list(self.selected_addons.all())
        if addons:
            addon_names = ", ".join([addon.name for addon in addons])
            desc += f" + {addon_names}"
        
        modifiers = list(self.selected_modifiers.all())
        if modifiers:
            modifier_names = ", ".join([modifier.name for modifier in modifiers])
            desc += f" ({modifier_names})"
        
        return desc


class OrderStatusHistory(models.Model):
    """
    Historial de cambios de estado de los pedidos
    """
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Historial de Estado'
        verbose_name_plural = 'Historial de Estados'
    
    def __str__(self):
        return f"{self.order.order_number} - {self.previous_status} → {self.new_status}" 