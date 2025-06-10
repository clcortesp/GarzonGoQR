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
    
    # 🆕 FASE 2: Estados granulares por item
    ITEM_STATUS_CHOICES = [
        # Estados iniciales
        ('pending', 'Pendiente de confirmación'),
        ('confirmed', 'Confirmado por restaurante'),
        
        # Estados de preparación - COCINA
        ('preparing_kitchen', 'En preparación - Cocina'),
        ('cooking', 'Cocinando'),
        ('plating', 'Emplantando'),
        ('kitchen_ready', 'Listo en cocina'),
        
        # Estados de preparación - BAR
        ('preparing_bar', 'En preparación - Bar'),
        ('mixing', 'Preparando bebida'),
        ('bar_ready', 'Listo en bar'),
        
        # Estados finales
        ('ready', 'Listo para servir'),
        ('served', 'Servido al cliente'),
        ('cancelled', 'Cancelado'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=ITEM_STATUS_CHOICES,
        default='pending',
        help_text="Estado específico de este item"
    )
    
    # 🆕 Área responsable del item (auto-detectada)
    responsible_area = models.CharField(
        max_length=20,
        choices=[
            ('kitchen', 'Cocina'),
            ('bar', 'Bar'),
            ('waiter', 'Mesero'),
        ],
        blank=True,
        help_text="Área responsable de preparar este item"
    )
    
    # 🆕 Tiempos de preparación específicos
    preparation_started_at = models.DateTimeField(null=True, blank=True)
    preparation_completed_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    
    # 🆕 Tiempo estimado para este item específico
    estimated_prep_time = models.PositiveIntegerField(
        default=15,
        help_text="Tiempo estimado de preparación en minutos para este item"
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
    
    # 🆕 FASE 2: Métodos para estados granulares
    
    def save(self, *args, **kwargs):
        """Override save para auto-detectar área responsable"""
        if not self.responsible_area:
            self.responsible_area = self.detect_responsible_area()
        
        if not self.estimated_prep_time or self.estimated_prep_time == 15:
            self.estimated_prep_time = self.calculate_estimated_prep_time()
        
        super().save(*args, **kwargs)
    
    def detect_responsible_area(self):
        """Auto-detectar qué área debe preparar este item"""
        category = self.menu_item.category.lower() if self.menu_item.category else ''
        
        # Categorías de bar
        bar_categories = ['bebidas', 'drinks', 'bar', 'cocktails', 'jugos', 'cafeteria']
        if any(cat in category for cat in bar_categories):
            return 'bar'
        
        # Todo lo demás va a cocina por defecto
        return 'kitchen'
    
    def calculate_estimated_prep_time(self):
        """Calcular tiempo estimado basado en el tipo de item"""
        if self.responsible_area == 'bar':
            return 5  # Bebidas son más rápidas
        elif self.menu_item.category and 'pizza' in self.menu_item.category.lower():
            return 25  # Pizzas toman más tiempo
        else:
            return 15  # Tiempo por defecto
    
    @property
    def status_for_area(self):
        """Estado formateado para el área responsable"""
        status_display = self.get_status_display()
        
        if self.responsible_area == 'kitchen':
            return status_display.replace('Cocina', '').replace(' - ', '').strip()
        elif self.responsible_area == 'bar':
            return status_display.replace('Bar', '').replace(' - ', '').strip()
        
        return status_display
    
    @property
    def can_start_preparation(self):
        """Verificar si puede empezar preparación"""
        return self.status in ['confirmed']
    
    @property
    def is_in_preparation(self):
        """Verificar si está en preparación"""
        return self.status in ['preparing_kitchen', 'cooking', 'plating', 'preparing_bar', 'mixing']
    
    @property
    def is_ready_for_service(self):
        """Verificar si está listo para servir"""
        return self.status in ['kitchen_ready', 'bar_ready', 'ready']
    
    def start_preparation(self):
        """Iniciar preparación del item"""
        from django.utils import timezone
        
        if self.can_start_preparation:
            if self.responsible_area == 'kitchen':
                self.status = 'preparing_kitchen'
            elif self.responsible_area == 'bar':
                self.status = 'preparing_bar'
            
            self.preparation_started_at = timezone.now()
            self.save()
            return True
        return False
    
    def mark_ready(self):
        """Marcar item como listo"""
        from django.utils import timezone
        
        if self.is_in_preparation:
            if self.responsible_area == 'kitchen':
                self.status = 'kitchen_ready'
            elif self.responsible_area == 'bar':
                self.status = 'bar_ready'
            else:
                self.status = 'ready'
            
            self.preparation_completed_at = timezone.now()
            self.save()
            return True
        return False
    
    def mark_served(self):
        """Marcar item como servido"""
        from django.utils import timezone
        
        if self.is_ready_for_service:
            self.status = 'served'
            self.served_at = timezone.now()
            self.save()
            return True
        return False


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