from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from restaurants.models import Restaurant
from menu.cart import Cart
from .models import Order, OrderItem, OrderStatusHistory
from .forms import CheckoutForm, OrderStatusUpdateForm, CustomerReviewForm

logger = logging.getLogger(__name__)


class CheckoutView(object):
    """
    Vista para el proceso de checkout
    """
    
    def get(self, request, tenant_slug):
        """
        Mostrar el formulario de checkout
        """
        try:
            # El middleware ya inyecta restaurant en el request
            restaurant = request.restaurant
            cart = Cart(request)
            
            # Verificar que el carrito no esté vacío
            if not cart:
                messages.warning(request, 'Tu carrito está vacío. Agrega algunos productos antes de continuar.')
                return redirect('menu:menu_list', tenant_slug=tenant_slug)
            
            # Calcular precios
            cart_data = cart.get_cart_data()
            
            form = CheckoutForm()
            
            context = {
                'restaurant': restaurant,
                'cart': cart_data,
                'form': form,
                'cart_total': cart.get_total_price(),
                'cart_count': len(cart)
            }
            
            return render(request, 'orders/checkout.html', context)
            
        except Exception as e:
            logger.error(f"Error en checkout GET: {e}")
            messages.error(request, 'Error al cargar el formulario de pedido.')
            return redirect('menu:menu_list', tenant_slug=tenant_slug)
    
    def post(self, request, tenant_slug):
        """
        Procesar el checkout y crear la orden
        """
        try:
            # El middleware ya inyecta restaurant en el request
            restaurant = request.restaurant
            cart = Cart(request)
            
            # Verificar que el carrito no esté vacío
            if not cart:
                messages.warning(request, 'Tu carrito está vacío.')
                return redirect('menu:menu_list', tenant_slug=tenant_slug)
            
            form = CheckoutForm(request.POST)
            
            if form.is_valid():
                # Crear la orden con transacción
                with transaction.atomic():
                    order = self._create_order_from_cart(form, restaurant, cart, request)
                    
                    # Limpiar el carrito
                    cart.clear()
                    
                    messages.success(request, f'¡Pedido realizado exitosamente! Número de orden: {order.order_number}')
                    return redirect('orders:order_detail', tenant_slug=tenant_slug, order_id=order.id)
            
            else:
                # Si hay errores en el formulario, mostrarlos
                cart_data = cart.get_cart_data()
                context = {
                    'restaurant': restaurant,
                    'cart': cart_data,
                    'form': form,
                    'cart_total': cart.get_total_price(),
                    'cart_count': len(cart)
                }
                return render(request, 'orders/checkout.html', context)
        
        except Exception as e:
            logger.error(f"Error en checkout POST: {e}")
            messages.error(request, 'Error al procesar el pedido. Inténtalo de nuevo.')
            return redirect('orders:checkout', tenant_slug=tenant_slug)
    
    def _create_order_from_cart(self, form, restaurant, cart, request):
        """
        Crear orden y items a partir del carrito
        """
        # Calcular precios
        subtotal = cart.get_total_price()
        tax_rate = Decimal('0.19')  # 19% IVA (configurable)
        tax_amount = subtotal * tax_rate
        
        # Calcular fee de delivery si aplica
        delivery_fee = Decimal('0')
        if form.cleaned_data['order_type'] == 'delivery':
            delivery_fee = Decimal('5000')  # Fee fijo de delivery (configurable)
        
        total_amount = subtotal + tax_amount + delivery_fee
        
        # Crear la orden
        order = form.save(commit=False)
        order.restaurant = restaurant
        order.subtotal = subtotal
        order.tax_amount = tax_amount
        order.delivery_fee = delivery_fee
        order.total_amount = total_amount
        
        # Asignar usuario si está autenticado
        if request.user.is_authenticated:
            order.customer_user = request.user
        
        order.save()
        
        # Crear items de la orden usando el iterador que incluye total_price
        for item_data in cart:
            self._create_order_item(order, item_data)
        
        # Crear historial de estado
        OrderStatusHistory.objects.create(
            order=order,
            new_status='pending',
            notes='Pedido creado desde el carrito'
        )
        
        return order
    
    def _create_order_item(self, order, item_data):
        """
        Crear un item de orden a partir de datos del carrito
        """
        from menu.models import MenuItem, MenuVariant, MenuAddon, MenuModifier
        
        menu_item = MenuItem.objects.get(id=item_data['menu_item_id'])
        
        # Crear el item de orden
        order_item = OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price'],
            variant_price=item_data.get('variant_price', 0),
            addons_price=item_data.get('addons_price', 0),
            modifiers_price=item_data.get('modifiers_price', 0),
            total_price=item_data['total_price'],
            special_instructions=item_data.get('special_instructions', '')
        )
        
        # Agregar variante si existe
        if item_data.get('variant_id'):
            variant = MenuVariant.objects.get(id=item_data['variant_id'])
            order_item.selected_variant = variant
            order_item.save()
        
        # Agregar addons
        if item_data.get('addon_ids'):
            addons = MenuAddon.objects.filter(id__in=item_data['addon_ids'])
            order_item.selected_addons.add(*addons)
        
        # Agregar modificadores
        if item_data.get('modifier_ids'):
            modifiers = MenuModifier.objects.filter(id__in=item_data['modifier_ids'])
            order_item.selected_modifiers.add(*modifiers)


def checkout(request, tenant_slug):
    """
    Vista función para el proceso de checkout
    """

    
    # El middleware ya inyecta restaurant en el request
    restaurant = request.restaurant
    cart = Cart(request)
    
    print(f"🔍 Restaurant: {restaurant.name}")
    print(f"🔍 Cart items: {len(cart)}")
    
    # Verificar que el carrito no esté vacío
    if not cart:
        messages.warning(request, 'Tu carrito está vacío. Agrega algunos productos antes de continuar.')
        # Redirigir al menú usando URL absoluta
        return redirect(f'/{tenant_slug}/menu/')
    
    if request.method == 'POST':
        print("🔍 POST request received!")
        print(f"🔍 POST data: {request.POST}")
        
        form = CheckoutForm(request.POST)
        print(f"🔍 Form valid: {form.is_valid()}")
        
        # Si el pedido viene de QR y se crea exitosamente, actualizar estadísticas de la mesa
        if form.is_valid():
            selected_table_info = request.session.get('selected_table')
            if selected_table_info:
                try:
                    from restaurants.models import Table, TableScanLog
                    table = Table.objects.get(id=selected_table_info['table_id'])
                    table.increment_order_count()
                    
                    # Marcar el escaneo como que resultó en pedido
                    scan_log_id = selected_table_info.get('scan_log_id')
                    if scan_log_id:
                        scan_log = TableScanLog.objects.get(id=scan_log_id)
                        scan_log.resulted_in_order = True
                        scan_log.save()
                        
                    print(f"🔍 Mesa {table.number} actualizada - pedido desde QR")
                except Exception as e:
                    print(f"🔍 Error actualizando mesa QR: {e}")
        
        if form.is_valid():
            print("🔍 Form is valid, creating order...")
            try:
                # Crear la orden con transacción
                with transaction.atomic():
                    order = _create_order_from_cart(form, restaurant, cart, request)
                    print(f"🔍 Order created: #{order.order_number}")
                    
                    # Limpiar el carrito
                    cart.clear()
                    print("🔍 Cart cleared")
                    
                    messages.success(request, f'¡Pedido realizado exitosamente! Número de orden: {order.order_number}')
                    return redirect('orders:order_detail', tenant_slug=tenant_slug, order_id=order.id)
                    
            except Exception as e:
                print(f"❌ Error en checkout POST: {e}")
                logger.error(f"Error en checkout POST: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error al procesar el pedido: {str(e)}')
        else:
            print("🚨 ❌ FORMULARIO INVÁLIDO - ESTA ES LA CAUSA DEL REFRESH!")
            print(f"❌ Form errors completos: {form.errors}")
            print(f"❌ Form non-field errors: {form.non_field_errors()}")
            
            # Debug detallado de cada campo
            print("🔍 ANÁLISIS DETALLADO DE ERRORES:")
            for field, errors in form.errors.items():
                print(f"    Campo '{field}': {list(errors)}")
                for error in errors:
                    print(f"      - {error}")
                    messages.error(request, f'{field}: {error}')
            
            print("🚨 RENDERIZANDO PÁGINA CON ERRORES (esto causa el 'refresh')")
    else:
        print("🔍 GET request, showing form")
        form = CheckoutForm()
    
    # Calcular precios
    cart_data = cart.get_cart_data()
    
    context = {
        'restaurant': restaurant,
        'cart': cart_data,
        'form': form,
        'cart_total': cart.get_total_price(),
        'cart_count': len(cart)
    }
    
    print(f"🔍 Rendering template with context")
    return render(request, 'orders/checkout.html', context)





def _create_order_from_cart(form, restaurant, cart, request):
    """
    Crear orden y items a partir del carrito
    """
    # Calcular precios
    subtotal = cart.get_total_price()
    tax_rate = Decimal('0.19')  # 19% IVA (configurable)
    tax_amount = subtotal * tax_rate
    
    # Calcular fee de delivery si aplica
    delivery_fee = Decimal('0')
    if form.cleaned_data['order_type'] == 'delivery':
        delivery_fee = Decimal('5000')  # Fee fijo de delivery (configurable)
    
    total_amount = subtotal + tax_amount + delivery_fee
    
    # Crear la orden
    order = form.save(commit=False)
    order.restaurant = restaurant
    order.subtotal = subtotal
    order.tax_amount = tax_amount
    order.delivery_fee = delivery_fee
    order.total_amount = total_amount
    
    # Asignar usuario si está autenticado
    if request.user.is_authenticated:
        order.customer_user = request.user
    
    order.save()
    
    # Crear items de la orden usando el iterador que incluye total_price
    for item_data in cart:
        _create_order_item(order, item_data)
    
    # Crear historial de estado
    OrderStatusHistory.objects.create(
        order=order,
        new_status='pending',
        notes='Pedido creado desde el carrito'
    )
    
    return order


def _create_order_item(order, item_data):
    """
    Crear un item de orden a partir de datos del carrito
    """
    from menu.models import MenuItem, MenuVariant, MenuAddon, MenuModifier
    
    menu_item = MenuItem.objects.get(id=item_data['menu_item_id'])
    
    # Crear el item de orden
    order_item = OrderItem.objects.create(
        order=order,
        menu_item=menu_item,
        quantity=item_data['quantity'],
        unit_price=item_data['unit_price'],  # Cambio de base_price a unit_price
        variant_price=item_data.get('variant_price', '0'),
        addons_price=item_data.get('addon_price', '0'),  # Era addons_price, pero en cart es addon_price
        modifiers_price=item_data.get('modifier_price', '0'),  # Era modifiers_price, pero en cart es modifier_price
        total_price=item_data['total_price'],
        special_instructions=item_data.get('special_instructions', '')
    )
    
    # Agregar variante si existe
    if item_data.get('variant_id'):
        variant = MenuVariant.objects.get(id=item_data['variant_id'])
        order_item.selected_variant = variant
        order_item.save()
    
    # Agregar addons
    if item_data.get('addon_ids'):
        addons = MenuAddon.objects.filter(id__in=item_data['addon_ids'])
        order_item.selected_addons.add(*addons)
    
    # Agregar modificadores
    if item_data.get('modifier_ids'):
        modifiers = MenuModifier.objects.filter(id__in=item_data['modifier_ids'])
        order_item.selected_modifiers.add(*modifiers)


checkout_view = CheckoutView()


class OrderDetailView(DetailView):
    """
    Vista de detalle de una orden
    """
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'
    pk_url_kwarg = 'order_id'
    
    def get_object(self, queryset=None):
        order_id = self.kwargs.get('order_id')
        
        try:
            # El middleware ya inyecta restaurant en el request
            restaurant = self.request.restaurant
            order = get_object_or_404(Order, id=order_id, restaurant=restaurant)
            return order
        except:
            raise Http404("Pedido no encontrado")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['restaurant'] = self.object.restaurant
        context['items'] = self.object.items.all().prefetch_related(
            'selected_addons', 'selected_modifiers'
        )
        return context


class RestaurantOrdersListView(LoginRequiredMixin, ListView):
    """
    Lista de pedidos para el restaurante (dashboard)
    """
    model = Order
    template_name = 'orders/restaurant_orders.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        # El middleware ya inyecta restaurant en el request
        restaurant = self.request.restaurant
        
        # Verificar que el usuario tenga permisos
        if not (self.request.user.is_superuser or 
                restaurant.owner == self.request.user):
            raise Http404("No tienes permisos para ver estos pedidos")
        
        queryset = Order.objects.filter(restaurant=restaurant).select_related('restaurant')
        
        # Filtros
        status = self.request.GET.get('status')
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        order_type = self.request.GET.get('order_type')
        if order_type and order_type != 'all':
            queryset = queryset.filter(order_type=order_type)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # El middleware ya inyecta restaurant en el request
        restaurant = self.request.restaurant
        
        context['restaurant'] = restaurant
        context['status_choices'] = Order.STATUS_CHOICES
        context['order_type_choices'] = Order.ORDER_TYPE_CHOICES
        context['current_status'] = self.request.GET.get('status', 'all')
        context['current_order_type'] = self.request.GET.get('order_type', 'all')
        
        # Estadísticas del día
        today = timezone.now().date()
        today_orders = Order.objects.filter(
            restaurant=restaurant,
            created_at__date=today
        )
        
        context['today_stats'] = {
            'total_orders': today_orders.count(),
            'pending_orders': today_orders.filter(status='pending').count(),
            'confirmed_orders': today_orders.filter(status='confirmed').count(),
            'preparing_orders': today_orders.filter(status='preparing').count(),
            'ready_orders': today_orders.filter(status='ready').count(),
            'total_revenue': sum(order.total_amount for order in today_orders.filter(status__in=['delivered', 'ready']))
        }
        
        return context


@login_required
@require_POST
def update_order_status(request, tenant_slug, order_id):
    """
    Actualizar estado de una orden (AJAX)
    """
    try:
        # El middleware ya inyecta restaurant en el request
        restaurant = request.restaurant
        order = get_object_or_404(Order, id=order_id, restaurant=restaurant)
        
        # Verificar permisos
        if not (request.user.is_superuser or 
                restaurant.owner == request.user):
            return JsonResponse({'success': False, 'error': 'Sin permisos'})
        
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if new_status not in dict(Order.STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'Estado inválido'})
        
        # Guardar estado anterior para el historial
        previous_status = order.status
        
        # Actualizar timestamps según el estado
        now = timezone.now()
        if new_status == 'confirmed' and not order.confirmed_at:
            order.confirmed_at = now
        elif new_status == 'ready' and not order.ready_at:
            order.ready_at = now
        elif new_status == 'delivered' and not order.delivered_at:
            order.delivered_at = now
        
        # Actualizar orden
        order.status = new_status
        order.save()
        
        # Crear registro en el historial
        OrderStatusHistory.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=request.user,
            notes=notes
        )
        
        return JsonResponse({
            'success': True,
            'new_status': new_status,
            'status_display': order.get_status_display(),
            'message': f'Estado actualizado a: {order.get_status_display()}'
        })
        
    except Exception as e:
        logger.error(f"Error actualizando estado de orden: {e}")
        return JsonResponse({'success': False, 'error': 'Error interno del servidor'})


def order_tracking(request, tenant_slug, order_id):
    """
    Página de seguimiento del pedido para el cliente
    """
    try:
        # El middleware ya inyecta restaurant en el request
        restaurant = request.restaurant
        order = get_object_or_404(Order, id=order_id, restaurant=restaurant)
        
        # Obtener historial de estados
        status_history = order.status_history.all()
        
        context = {
            'restaurant': restaurant,
            'order': order,
            'status_history': status_history,
            'estimated_ready_time': order.estimated_ready_time
        }
        
        return render(request, 'orders/order_tracking.html', context)
        
    except Exception as e:
        logger.error(f"Error en seguimiento de orden: {e}")
        messages.error(request, 'No se pudo cargar el seguimiento del pedido.')
        return redirect('restaurants:menu', tenant_slug=tenant_slug)


def redirect_to_cart(request):
    """
    Vista de redirección al carrito del menú
    """
    tenant_slug = request.tenant.slug
    return redirect(f'/{tenant_slug}/menu/cart/')


 