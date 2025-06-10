from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models import Q, Prefetch, Count
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from restaurants.middleware import get_current_tenant, get_current_restaurant
from restaurants.views import TenantMixin
from .models import MenuCategory, MenuItem, MenuVariant, MenuAddon, MenuModifier
from .cart import Cart


class MenuListView(TenantMixin, TemplateView):
    """Vista principal del menú público"""
    template_name = 'menu/menu_list.html'
    
    def dispatch(self, request, *args, **kwargs):
        print(f"🔍 MenuListView.dispatch() - URL: {request.path}")
        print(f"🔍 MenuListView.dispatch() - Tenant: {getattr(request, 'tenant', 'NO_TENANT')}")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Debug: verificar que llegamos a la vista correcta
        print(f"🔍 MenuListView.get_context_data() ejecutándose para tenant: {getattr(self.request, 'tenant', 'NO_TENANT')}")
        
        # 🎯 OBTENER INFORMACIÓN DE SESIÓN DE MESA
        from restaurants.table_session_manager import TableSessionManager
        table_session = TableSessionManager.get_active_session(self.request)
        
        # Información de mesa activa
        active_table_info = None
        if table_session:
            from restaurants.models import Table
            try:
                table = Table.objects.get(id=table_session['table_id'])
                active_table_info = {
                    'number': table.number,
                    'name': table.display_name,
                    'location': table.location or '',
                    'session_expires': table_session.get('expires_at'),
                    'session_active_time': table_session.get('created_at')
                }
                print(f"🪑 Mesa activa detectada: {active_table_info}")
            except Table.DoesNotExist:
                print("❌ Mesa no encontrada en DB")
        
        # Obtener categorías activas con sus productos
        try:
            categories = MenuCategory.objects.filter(
                tenant=self.request.tenant,
                is_active=True
            ).prefetch_related(
                Prefetch(
                    'menu_items',
                    queryset=MenuItem.objects.filter(
                        is_available=True
                    ).prefetch_related('variants', 'available_addons', 'available_modifiers')
                )
            ).order_by('order', 'name')
            
            print(f"🔍 Categorías encontradas: {categories.count()}")
        except Exception as e:
            print(f"❌ Error al obtener categorías: {e}")
            categories = MenuCategory.objects.none()
        
        # Productos destacados
        featured_items = MenuItem.objects.filter(
            tenant=self.request.tenant,
            is_featured=True,
            is_available=True
        ).select_related('category')[:6]
        
        context.update({
            'categories': categories,
            'featured_items': featured_items,
            'page_title': f'Menú - {self.request.restaurant.name}',
            'show_qr_info': True,  # Para mostrar info de QR
            'active_table_info': active_table_info,  # 🆕 Info de mesa activa
            'has_active_session': table_session is not None,  # 🆕 Flag de sesión
        })
        return context


class MenuItemDetailView(TenantMixin, DetailView):
    """Vista detallada de un producto del menú"""
    model = MenuItem
    template_name = 'menu/menu_item_detail.html'
    context_object_name = 'item'
    slug_field = 'slug'
    slug_url_kwarg = 'item_slug'
    
    def get_queryset(self):
        return MenuItem.objects.filter(
            tenant=self.request.tenant,
            is_available=True
        ).select_related('category').prefetch_related(
            'variants', 'available_addons', 'available_modifiers'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        
        # Variantes del producto (tamaños, tipos, etc.)
        variants = item.variants.filter(is_available=True).order_by('price_modifier')
        
        # Addons disponibles para este producto
        addons = item.available_addons.filter(is_available=True).order_by('addon_type', 'price')
        
        # Modificadores disponibles (sin cebolla, etc.)
        modifiers = item.available_modifiers.filter(is_available=True).order_by('name')
        
        # Productos relacionados de la misma categoría
        related_items = MenuItem.objects.filter(
            tenant=self.request.tenant,
            category=item.category,
            is_available=True
        ).exclude(id=item.id)[:4]
        
        # Verificar si el item tiene descuento
        discount_info = None
        if item.has_discount:
            discount_info = {
                'original_price': item.base_price,
                'discounted_price': item.current_price,
                'percentage': item.discount_percentage,
                'savings': item.base_price - item.current_price
            }
        
        context.update({
            'variants': variants,
            'addons': addons,
            'modifiers': modifiers,
            'related_items': related_items,
            'discount_info': discount_info,
            'page_title': f'{item.name} - {self.request.restaurant.name}',
        })
        return context


class MenuCategoryView(TenantMixin, TemplateView):
    """Vista de una categoría específica"""
    template_name = 'menu/menu_category.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = kwargs.get('category_slug')
        
        category = get_object_or_404(
            MenuCategory,
            tenant=self.request.tenant,
            slug=category_slug,
            is_active=True
        )
        
        items = MenuItem.objects.filter(
            tenant=self.request.tenant,
            category=category,
            is_available=True
        ).prefetch_related('variants', 'available_addons').order_by('order', 'name')
        
        # Otras categorías para navegación
        other_categories = MenuCategory.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).exclude(id=category.id).order_by('order', 'name')
        
        context.update({
            'category': category,
            'items': items,
            'other_categories': other_categories,
            'page_title': f'{category.name} - {self.request.restaurant.name}',
        })
        return context


# === VISTAS DE GESTIÓN (DASHBOARD) ===

class MenuManagementView(LoginRequiredMixin, TenantMixin, TemplateView):
    """Dashboard para gestión del menú"""
    template_name = 'menu/management/menu_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas del menú
        total_items = MenuItem.objects.filter(tenant=self.request.tenant).count()
        active_items = MenuItem.objects.filter(tenant=self.request.tenant, is_available=True).count()
        featured_items = MenuItem.objects.filter(tenant=self.request.tenant, is_featured=True).count()
        categories_count = MenuCategory.objects.filter(tenant=self.request.tenant, is_active=True).count()
        
        # Productos con stock bajo
        low_stock_items = MenuItem.objects.filter(
            tenant=self.request.tenant,
            stock_quantity__lte=5,
            stock_quantity__isnull=False
        ).select_related('category')
        
        # Productos más populares (simulado - en el futuro con orders)
        popular_items = MenuItem.objects.filter(
            tenant=self.request.tenant,
            is_available=True
        ).order_by('-created_at')[:5]
        
        context.update({
            'total_items': total_items,
            'active_items': active_items,
            'featured_items': featured_items,
            'categories_count': categories_count,
            'low_stock_items': low_stock_items,
            'popular_items': popular_items,
            'page_title': 'Gestión del Menú',
            'is_dashboard': True,
        })
        return context


class MenuCategoriesManagementView(LoginRequiredMixin, TenantMixin, ListView):
    """Gestión de categorías del menú"""
    model = MenuCategory
    template_name = 'menu/management/categories_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return MenuCategory.objects.filter(
            tenant=self.request.tenant
        ).annotate(
            items_count=Count('menu_items')
        ).order_by('order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Gestión de Categorías',
            'is_dashboard': True,
        })
        return context


class MenuItemsManagementView(LoginRequiredMixin, TenantMixin, ListView):
    """Gestión de productos del menú"""
    model = MenuItem
    template_name = 'menu/management/items_list.html'
    context_object_name = 'items'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = MenuItem.objects.filter(
            tenant=self.request.tenant
        ).select_related('category').order_by('category__order', 'order', 'name')
        
        # Filtros
        search = self.request.GET.get('search')
        category = self.request.GET.get('category')
        status = self.request.GET.get('status')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        if category:
            queryset = queryset.filter(category__slug=category)
        
        if status == 'available':
            queryset = queryset.filter(is_available=True)
        elif status == 'unavailable':
            queryset = queryset.filter(is_available=False)
        elif status == 'featured':
            queryset = queryset.filter(is_featured=True)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Para los filtros
        categories = MenuCategory.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).order_by('order', 'name')
        
        context.update({
            'categories': categories,
            'current_search': self.request.GET.get('search', ''),
            'current_category': self.request.GET.get('category', ''),
            'current_status': self.request.GET.get('status', ''),
            'page_title': 'Gestión de Productos',
            'is_dashboard': True,
        })
        return context


# === API VIEWS ===

def menu_api(request, tenant_slug=None):
    """API para obtener el menú completo en formato JSON"""
    if not hasattr(request, 'tenant'):
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    
    categories_data = []
    categories = MenuCategory.objects.filter(
        tenant=request.tenant,
        is_active=True
    ).prefetch_related('menu_items').order_by('order', 'name')
    
    for category in categories:
        items_data = []
        items = category.menu_items.filter(is_available=True).order_by('order', 'name')
        
        for item in items:
            items_data.append({
                'id': str(item.id),
                'name': item.name,
                'slug': item.slug,
                'description': item.description,
                'short_description': item.short_description,
                'base_price': float(item.base_price),
                'current_price': float(item.current_price),
                'has_discount': item.has_discount,
                'discount_percentage': item.discount_percentage,
                'is_featured': item.is_featured,
                'preparation_time': item.preparation_time,
                'calories': item.calories,
                'is_vegetarian': item.is_vegetarian,
                'is_vegan': item.is_vegan,
                'is_gluten_free': item.is_gluten_free,
                'is_spicy': item.is_spicy,
                'allergens': item.allergens,
                'image': item.image.url if item.image else None,
                'is_in_stock': item.is_in_stock,
            })
        
        categories_data.append({
            'id': str(category.id),
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
            'image': category.image.url if category.image else None,
            'items': items_data,
        })
    
    return JsonResponse({
        'restaurant': {
            'name': request.restaurant.name,
            'slug': request.tenant.slug,
        },
        'categories': categories_data,
        'total_items': sum(len(cat['items']) for cat in categories_data),
    })





def menu_search_api(request, tenant_slug=None):
    """API para búsqueda de productos"""
    if not hasattr(request, 'tenant'):
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'error': 'Query too short'}, status=400)
    
    items = MenuItem.objects.filter(
        tenant=request.tenant,
        is_available=True
    ).filter(
        Q(name__icontains=query) | 
        Q(description__icontains=query) |
        Q(category__name__icontains=query)
    ).select_related('category')[:10]
    
    results = []
    for item in items:
        results.append({
            'id': str(item.id),
            'name': item.name,
            'slug': item.slug,
            'category': item.category.name,
            'price': float(item.current_price),
            'image': item.image.url if item.image else None,
            'is_featured': item.is_featured,
        })
    
    return JsonResponse({
        'query': query,
        'results': results,
        'count': len(results),
    })


# === VISTAS DEL CARRITO DE COMPRAS ===

class CartView(TenantMixin, TemplateView):
    """Vista del carrito de compras"""
    template_name = 'menu/cart.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        # Usar include_objects=True para templates que necesitan objetos MenuItem
        cart_data = cart.get_cart_data(include_objects=True)
        
        context.update({
            'cart': cart_data,
            'page_title': f'Carrito - {self.request.restaurant.name}',
        })
        return context


@require_POST
def cart_add(request, tenant_slug=None):
    """Agregar producto al carrito"""
    print(f"🛒 cart_add() - Path: {request.path}")
    print(f"🛒 cart_add() - Method: {request.method}")
    print(f"🛒 cart_add() - Tenant: {getattr(request, 'tenant', 'NO_TENANT')}")
    print(f"🛒 cart_add() - POST data: {dict(request.POST)}")
    
    if not hasattr(request, 'tenant'):
        print("❌ No hay tenant en request")
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    
    try:
        menu_item_id = request.POST.get('menu_item_id')
        quantity = int(request.POST.get('quantity', 1))
        variant_id = request.POST.get('variant_id', None)
        addon_ids = request.POST.get('addons', '').split(',') if request.POST.get('addons') else []
        modifier_ids = request.POST.getlist('modifiers')
        
        print(f"📊 Datos extraídos - Item: {menu_item_id}, Qty: {quantity}, Variant: {variant_id}")
        print(f"📊 Addons: {addon_ids}, Modifiers: {modifier_ids}")
        
        # Limpiar IDs vacíos
        addon_ids = [aid for aid in addon_ids if aid.strip()]
        modifier_ids = [mid for mid in modifier_ids if mid.strip()]
        
        menu_item = get_object_or_404(MenuItem, id=menu_item_id, tenant=request.tenant)
        print(f"✅ Producto encontrado: {menu_item.name}")
        
        cart = Cart(request)
        print(f"🛒 Cart inicializado: {len(cart)} items")
        
        cart.add(
            menu_item=menu_item,
            quantity=quantity,
            variant_id=variant_id,
            addon_ids=addon_ids,
            modifier_ids=modifier_ids
        )
        print(f"✅ Producto agregado al carrito")
        
        # Respuesta exitosa
        cart_data = cart.get_cart_data(for_json=True)  # Solo datos básicos para JSON
        print(f"📊 Cart data: {cart_data}")
        
        return JsonResponse({
            'success': True,
            'message': f'{menu_item.name} agregado al carrito',
            'cart_total_items': cart_data['total_quantity'],
            'cart_total_price': cart_data['total_price']
        })
        
    except MenuItem.DoesNotExist:
        print("❌ Producto no encontrado")
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    except Exception as e:
        print(f"❌ Error en cart_add: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=400)


@require_POST
def cart_remove(request, tenant_slug=None):
    """Remover producto del carrito"""
    if not hasattr(request, 'tenant'):
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    
    try:
        cart_item_id = request.POST.get('cart_item_id')
        cart = Cart(request)
        cart.remove(cart_item_id)
        
        cart_data = cart.get_cart_data(for_json=True)
        return JsonResponse({
            'success': True,
            'message': 'Producto removido del carrito',
            'cart_total_items': cart_data['total_quantity'],
            'cart_total_price': cart_data['total_price']
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_POST
def cart_update(request, tenant_slug=None):
    """Actualizar cantidad de producto en el carrito"""
    if not hasattr(request, 'tenant'):
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    
    try:
        cart_item_id = request.POST.get('cart_item_id')
        quantity = int(request.POST.get('quantity', 1))
        
        cart = Cart(request)
        cart.update(cart_item_id, quantity)
        
        cart_data = cart.get_cart_data(for_json=True)
        return JsonResponse({
            'success': True,
            'message': 'Carrito actualizado',
            'cart_total_items': cart_data['total_quantity'],
            'cart_total_price': cart_data['total_price']
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def cart_clear(request, tenant_slug=None):
    """Vaciar el carrito"""
    if not hasattr(request, 'tenant'):
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    
    cart = Cart(request)
    cart.clear()
    
    return JsonResponse({
        'success': True,
        'message': 'Carrito vaciado',
        'cart_total_items': 0,
        'cart_total_price': '0.00'
    })
