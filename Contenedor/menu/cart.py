from decimal import Decimal
from django.conf import settings
from .models import MenuItem, MenuVariant, MenuAddon, MenuModifier


class Cart:
    """
    Clase para manejar el carrito de compras usando sesiones
    """
    
    def __init__(self, request):
        """
        Inicializar el carrito
        """
        self.session = request.session
        self.tenant = getattr(request, 'tenant', None)
        cart = self.session.get(settings.CART_SESSION_ID)
        
        if not cart:
            # Crear carrito vacío en la sesión
            cart = self.session[settings.CART_SESSION_ID] = {}
        
        self.cart = cart
    
    def add(self, menu_item, quantity=1, variant_id=None, addon_ids=None, modifier_ids=None, override_quantity=False):
        """
        Agregar un producto al carrito o actualizar su cantidad
        """
        addon_ids = addon_ids or []
        modifier_ids = modifier_ids or []
        
        # Crear un ID único para este item específico (producto + variantes + addons + modifiers)
        item_id = str(menu_item.id)
        variant_key = f"variant_{variant_id}" if variant_id else "no_variant"
        addons_key = f"addons_{'_'.join(sorted(addon_ids))}" if addon_ids else "no_addons"
        modifiers_key = f"modifiers_{'_'.join(sorted(modifier_ids))}" if modifier_ids else "no_modifiers"
        
        cart_item_id = f"{item_id}_{variant_key}_{addons_key}_{modifiers_key}"
        
        # Calcular precio base
        base_price = menu_item.current_price
        
        # Agregar precio de variante
        variant_price = Decimal('0')
        variant_name = None
        if variant_id:
            try:
                variant = MenuVariant.objects.get(id=variant_id, menu_item=menu_item)
                variant_price = variant.price_modifier
                variant_name = variant.name
            except MenuVariant.DoesNotExist:
                pass
        
        # Agregar precios de addons
        addon_price = Decimal('0')
        addon_names = []
        if addon_ids:
            addons = MenuAddon.objects.filter(id__in=addon_ids, menu_items=menu_item)
            for addon in addons:
                addon_price += addon.price
                addon_names.append(addon.name)
        
        # Agregar precios de modificadores
        modifier_price = Decimal('0')
        modifier_names = []
        if modifier_ids:
            modifiers = MenuModifier.objects.filter(id__in=modifier_ids, menu_items=menu_item)
            for modifier in modifiers:
                modifier_price += modifier.price_modifier
                modifier_names.append(modifier.name)
        
        # Precio total por unidad
        unit_price = base_price + variant_price + addon_price + modifier_price
        
        if cart_item_id in self.cart:
            if override_quantity:
                self.cart[cart_item_id]['quantity'] = quantity
            else:
                self.cart[cart_item_id]['quantity'] += quantity
        else:
            self.cart[cart_item_id] = {
                'menu_item_id': str(menu_item.id),
                'name': menu_item.name,
                'quantity': quantity,
                'unit_price': str(unit_price),
                'base_price': str(base_price),
                'variant_id': variant_id,
                'variant_name': variant_name,
                'variant_price': str(variant_price),
                'addon_ids': addon_ids,
                'addon_names': addon_names,
                'addon_price': str(addon_price),
                'modifier_ids': modifier_ids,
                'modifier_names': modifier_names,
                'modifier_price': str(modifier_price),
                'image_url': menu_item.image.url if menu_item.image else None,
                'category': menu_item.category.name,
            }
        
        self.save()
    
    def save(self):
        """
        Marcar la sesión como modificada para asegurar que se guarde
        """
        self.session.modified = True
    
    def remove(self, cart_item_id):
        """
        Remover un producto del carrito
        """
        if cart_item_id in self.cart:
            del self.cart[cart_item_id]
            self.save()
    
    def update(self, cart_item_id, quantity):
        """
        Actualizar la cantidad de un producto en el carrito
        """
        if cart_item_id in self.cart:
            if quantity <= 0:
                self.remove(cart_item_id)
            else:
                self.cart[cart_item_id]['quantity'] = quantity
                self.save()
    
    def clear(self):
        """
        Vaciar el carrito
        """
        del self.session[settings.CART_SESSION_ID]
        self.save()
    
    def __iter__(self):
        """
        Iterar sobre los items del carrito y obtener los productos de la base de datos
        """
        menu_item_ids = [item['menu_item_id'] for item in self.cart.values()]
        menu_items = MenuItem.objects.filter(id__in=menu_item_ids)
        cart = self.cart.copy()
        
        for cart_item_id, item in cart.items():
            menu_item = next((mi for mi in menu_items if str(mi.id) == item['menu_item_id']), None)
            if menu_item:
                # Incluir el objeto MenuItem para templates (necesario para cart.html)
                item['menu_item'] = menu_item
                item['cart_item_id'] = cart_item_id  # Agregar ID único del carrito
                unit_price = Decimal(item['unit_price'])
                total_price = unit_price * item['quantity']
                
                # Convertir precios a string para serialización JSON
                item['unit_price'] = str(unit_price)
                item['total_price'] = str(total_price)
                
                yield item
    
    def __len__(self):
        """
        Contar todos los items en el carrito
        """
        return sum(item['quantity'] for item in self.cart.values())
    
    def get_total_price(self):
        """
        Calcular el precio total del carrito
        """
        return sum(Decimal(item['unit_price']) * item['quantity'] for item in self.cart.values())
    
    def get_total_items(self):
        """
        Obtener el número total de items únicos en el carrito
        """
        return len(self.cart)
    
    def get_cart_data(self, for_json=False):
        """
        Obtener todos los datos del carrito para templates
        """
        if for_json:
            # Para respuestas JSON, solo devolver datos básicos sin objetos complejos
            return {
                'total_price': str(self.get_total_price()),
                'total_quantity': len(self),
                'total_items': self.get_total_items(),
                'item_count': len(self.cart),
            }
        else:
            # Para templates, incluir los items completos
            items = list(self)
            return {
                'items': items,
                'total_price': str(self.get_total_price()),
                'total_quantity': len(self),
                'total_items': self.get_total_items(),
            } 