import uuid
from django.db import models
from django.contrib.auth.models import User
from restaurants.models import Tenant
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from PIL import Image


class MenuCategory(models.Model):
    """Categorías del menú (Entradas, Platos principales, Postres, etc.)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='menu_categories')
    
    name = models.CharField(max_length=100, verbose_name="Nombre de la categoría")
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    # Orden y visibilidad
    order = models.PositiveIntegerField(default=0, verbose_name="Orden de aparición")
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    
    # Imagen opcional
    image = models.ImageField(upload_to='menu/categories/', null=True, blank=True)
    
    # Horarios de disponibilidad
    available_from = models.TimeField(null=True, blank=True, verbose_name="Disponible desde")
    available_until = models.TimeField(null=True, blank=True, verbose_name="Disponible hasta")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Categoría de Menú'
        verbose_name_plural = 'Categorías de Menú'
        ordering = ['order', 'name']
        unique_together = [('tenant', 'slug')]
    
    def __str__(self):
        return f"{self.name} - {self.tenant.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    @property
    def active_items_count(self):
        return self.menu_items.filter(is_available=True).count()


class MenuItem(models.Model):
    """Elementos del menú (productos individuales)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='menu_items')
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='menu_items')
    
    # Info básica
    name = models.CharField(max_length=200, verbose_name="Nombre del producto")
    slug = models.SlugField(max_length=200)
    description = models.TextField(verbose_name="Descripción")
    short_description = models.CharField(max_length=150, blank=True, verbose_name="Descripción corta")
    
    # Precios
    base_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio base")
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                         verbose_name="Precio con descuento")
    
    # Disponibilidad
    is_available = models.BooleanField(default=True, verbose_name="Disponible")
    is_featured = models.BooleanField(default=False, verbose_name="Producto destacado")
    stock_quantity = models.PositiveIntegerField(null=True, blank=True, verbose_name="Cantidad en stock")
    
    # Multimedia
    image = models.ImageField(upload_to='menu/items/', null=True, blank=True)
    gallery_images = models.JSONField(default=list, blank=True, verbose_name="Galería de imágenes")
    
    # Información nutricional/características
    calories = models.PositiveIntegerField(null=True, blank=True, verbose_name="Calorías")
    preparation_time = models.PositiveIntegerField(null=True, blank=True, verbose_name="Tiempo de preparación (minutos)")
    
    # Tags y alérgenos
    is_vegetarian = models.BooleanField(default=False, verbose_name="Vegetariano")
    is_vegan = models.BooleanField(default=False, verbose_name="Vegano")
    is_gluten_free = models.BooleanField(default=False, verbose_name="Sin gluten")
    is_spicy = models.BooleanField(default=False, verbose_name="Picante")
    allergens = models.JSONField(default=list, blank=True, verbose_name="Alérgenos")
    
    # Orden
    order = models.PositiveIntegerField(default=0, verbose_name="Orden en categoría")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Producto del Menú'
        verbose_name_plural = 'Productos del Menú'
        ordering = ['category__order', 'order', 'name']
        unique_together = [('tenant', 'slug')]
    
    def __str__(self):
        return f"{self.name} - {self.category.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.short_description:
            self.short_description = self.description[:150]
        super().save(*args, **kwargs)
    
    @property
    def current_price(self):
        """Precio actual (con descuento si aplica)"""
        return self.discounted_price if self.discounted_price else self.base_price
    
    @property
    def has_discount(self):
        return self.discounted_price and self.discounted_price < self.base_price
    
    @property
    def discount_percentage(self):
        if self.has_discount:
            return round(((self.base_price - self.discounted_price) / self.base_price) * 100)
        return 0
    
    @property
    def is_in_stock(self):
        if self.stock_quantity is None:
            return True  # Stock ilimitado
        return self.stock_quantity > 0


class MenuVariant(models.Model):
    """Variantes de productos (Tamaños, tipos, etc.)"""
    
    VARIANT_TYPES = [
        ('SIZE', 'Tamaño'),
        ('TYPE', 'Tipo'),
        ('STYLE', 'Estilo'),
        ('OTHER', 'Otro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='variants')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='menu_variants')
    
    variant_type = models.CharField(max_length=20, choices=VARIANT_TYPES, default='SIZE')
    name = models.CharField(max_length=100, verbose_name="Nombre de la variante")
    
    # Modificación de precio
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name="Modificador de precio (+/-)")
    
    is_default = models.BooleanField(default=False, verbose_name="Variante por defecto")
    is_available = models.BooleanField(default=True, verbose_name="Disponible")
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Variante de Producto'
        verbose_name_plural = 'Variantes de Producto'
        ordering = ['variant_type', 'order', 'name']
        unique_together = [('menu_item', 'name')]
    
    def __str__(self):
        return f"{self.menu_item.name} - {self.name}"
    
    @property 
    def final_price(self):
        """Precio final con el modificador aplicado"""
        return self.menu_item.current_price + self.price_modifier


class MenuAddon(models.Model):
    """Extras/complementos para productos"""
    
    ADDON_TYPES = [
        ('INGREDIENT', 'Ingrediente extra'),
        ('SIDE', 'Acompañamiento'),
        ('SAUCE', 'Salsa'),
        ('DRINK', 'Bebida'),
        ('OTHER', 'Otro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='menu_addons')
    menu_items = models.ManyToManyField(MenuItem, related_name='available_addons',
                                       verbose_name="Productos compatibles")
    
    addon_type = models.CharField(max_length=20, choices=ADDON_TYPES, default='INGREDIENT')
    name = models.CharField(max_length=100, verbose_name="Nombre del extra")
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")
    
    is_available = models.BooleanField(default=True, verbose_name="Disponible")
    max_quantity = models.PositiveIntegerField(default=3, verbose_name="Cantidad máxima")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Extra/Complemento'
        verbose_name_plural = 'Extras/Complementos'
        ordering = ['addon_type', 'name']
    
    def __str__(self):
        return f"{self.name} (+${self.price})"


class MenuModifier(models.Model):
    """Modificadores de productos (Sin cebolla, Extra picante, etc.)"""
    
    MODIFIER_TYPES = [
        ('REMOVE', 'Quitar ingrediente'),
        ('ADD', 'Agregar extra'),
        ('STYLE', 'Estilo de preparación'),
        ('TEMPERATURE', 'Temperatura'),
        ('OTHER', 'Otro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='menu_modifiers')
    menu_items = models.ManyToManyField(MenuItem, related_name='available_modifiers',
                                       verbose_name="Productos compatibles")
    
    modifier_type = models.CharField(max_length=20, choices=MODIFIER_TYPES, default='REMOVE')
    name = models.CharField(max_length=100, verbose_name="Nombre del modificador")
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name="Modificador de precio (+/-)")
    
    is_available = models.BooleanField(default=True, verbose_name="Disponible")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Modificador'
        verbose_name_plural = 'Modificadores'
        ordering = ['modifier_type', 'name']
    
    def __str__(self):
        price_text = f" (${self.price_modifier:+})" if self.price_modifier != 0 else ""
        return f"{self.name}{price_text}"
