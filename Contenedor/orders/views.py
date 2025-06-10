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

from restaurants.models import Restaurant, Table
from restaurants.waiter_notifications import WaiterNotificationService
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
                return redirect(f'/{tenant_slug}/menu/')
            
            # 🎯 DETECTAR SESIÓN DE MESA ACTIVA (FASE 2: Integración completa)
            from restaurants.table_session_manager import TableSessionManager
            table_session = TableSessionManager.get_active_session(request)
            
            # 🔧 FASE 2: Usar método específico para templates (sin objetos complejos)
            cart_data = cart.get_items_with_objects()
            
            # Crear formulario con datos pre-llenos si hay sesión de mesa
            form_initial = {}
            table_info = None
            
            if table_session:
                # Es pedido desde mesa - pre-llenar datos
                from restaurants.models import Table
                try:
                    table = Table.objects.get(id=table_session['table_id'])
                    table_info = {
                        'number': table.number,
                        'name': table.display_name,
                        'location': table.location or ''
                    }
                    form_initial = {
                        'order_type': 'dine_in',  # Forzar tipo "en restaurante"
                        'table_number': table.display_name,  # Pre-llenar mesa
                    }
                except Table.DoesNotExist:
                    pass
            
            form = CheckoutForm(initial=form_initial)
            
            context = {
                'restaurant': restaurant,
                'tenant': restaurant.tenant,  # 🔧 FASE 2: Agregar tenant para base.html
                'cart': {'items': cart_data},  # 🔧 FASE 2: Estructura correcta para template
                'form': form,
                'cart_total': cart.get_total_price(),
                'cart_count': len(cart),
                'table_session': table_session,  # 🆕 Info de sesión
                'table_info': table_info,        # 🆕 Info de mesa
                'is_table_session': table_session is not None,  # 🆕 Flag
            }
            
            return render(request, 'orders/checkout.html', context)
            
        except Exception as e:
            logger.error(f"Error en checkout GET: {e}")
            messages.error(request, 'Error al cargar el formulario de pedido.')
            return redirect(f'/{tenant_slug}/menu/')
    
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
                return redirect('menu:list')
            
            form = CheckoutForm(request.POST)
            
            if form.is_valid():
                # Crear la orden con transacción
                with transaction.atomic():
                    order = self._create_order_from_cart(form, restaurant, cart, request)
                    
                    # Limpiar el carrito
                    cart.clear()
                    
                    messages.success(request, f'¡Pedido realizado exitosamente! Número de orden: {order.order_number}')
                    return redirect(f'/{tenant_slug}/orders/order/{order.id}/')
            
            else:
                # Si hay errores en el formulario, mostrarlos
                cart_data = cart.get_items_with_objects()
                context = {
                    'restaurant': restaurant,
                    'tenant': restaurant.tenant,  # 🔧 FASE 2: Agregar tenant para base.html
                    'cart': {'items': cart_data},  # 🔧 FASE 2: Estructura correcta para template
                    'form': form,
                    'cart_total': cart.get_total_price(),
                    'cart_count': len(cart)
                }
                return render(request, 'orders/checkout.html', context)
        
        except Exception as e:
            logger.error(f"Error en checkout POST: {e}")
            messages.error(request, 'Error al procesar el pedido. Inténtalo de nuevo.')
            return redirect(f'/{tenant_slug}/orders/checkout/')
    
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
        🆕 FASE 2: Integrado con estados granulares
        """
        from menu.models import MenuItem, MenuVariant, MenuAddon, MenuModifier
        
        menu_item = MenuItem.objects.get(id=item_data['menu_item_id'])
        
        # Crear el item de orden con estado inicial
        order_item = OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price'],
            variant_price=item_data.get('variant_price', 0),
            addons_price=item_data.get('addons_price', 0),
            modifiers_price=item_data.get('modifiers_price', 0),
            total_price=item_data['total_price'],
            special_instructions=item_data.get('special_instructions', ''),
            # 🆕 FASE 2: Estado inicial granular
            status='confirmed'  # Inmediatamente confirmado para preparación
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

    print(f"🔍 Checkout called with tenant_slug: '{tenant_slug}'")
    
    # El middleware ya inyecta restaurant en el request
    restaurant = request.restaurant
    cart = Cart(request)
    
    print(f"🔍 Restaurant: {restaurant.name}")
    print(f"🔍 Cart items: {len(cart)}")
    
    # 🎯 DETECTAR SESIÓN DE MESA ACTIVA
    from restaurants.table_session_manager import TableSessionManager
    table_session = TableSessionManager.get_active_session(request)
    
    # 🔧 INICIALIZAR table_info ANTES DE CUALQUIER LÓGICA
    table_info = None
    if table_session:
        # Es pedido desde mesa - obtener info de mesa
        from restaurants.models import Table
        try:
            table = Table.objects.get(id=table_session['table_id'])
            table_info = {
                'number': table.number,
                'name': table.display_name,
                'location': table.location or ''
            }
            print(f"🪑 Mesa detectada en sesión: {table.display_name}")
        except Table.DoesNotExist:
            print("❌ Mesa no encontrada en DB")
    
    # Verificar que el carrito no esté vacío
    if not cart:
        messages.warning(request, 'Tu carrito está vacío. Agrega algunos productos antes de continuar.')
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
                    print(f"🔍 Redirecting to: /{tenant_slug}/orders/order/{order.id}/")
                    return redirect(f'/{tenant_slug}/orders/order/{order.id}/')
                    
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
        
        # 🎯 CREAR FORMULARIO CON DATOS PRE-LLENOS SI HAY SESIÓN DE MESA
        form_initial = {}
        
        if table_session and table_info:
            form_initial = {
                'order_type': 'dine_in',  # Forzar tipo "en restaurante"
                'table_number': table_info['name'],  # Pre-llenar mesa
            }
        
        form = CheckoutForm(initial=form_initial)
    
    # 🔧 FASE 2: Obtener datos del carrito para template
    cart_data = cart.get_items_with_objects()
    
    context = {
        'restaurant': restaurant,
        'tenant': restaurant.tenant,  # 🔧 FASE 2: Agregar tenant para base.html
        'cart': {'items': cart_data},  # 🔧 FASE 2: Estructura correcta para template
        'form': form,
        'cart_total': cart.get_total_price(),
        'cart_count': len(cart),
        'table_session': table_session,  # 🆕 Info de sesión
        'table_info': table_info,        # 🆕 Info de mesa
        'is_table_session': table_session is not None,  # 🆕 Flag
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
    
    # 🆕 LÓGICA DE MESA Y GARZÓN
    # Si es dine_in y hay una mesa en la sesión (por QR), asignarla
    if form.cleaned_data['order_type'] == 'dine_in':
        # 🔧 USAR SISTEMA MODERNO TableSessionManager
        from restaurants.table_session_manager import TableSessionManager
        table_session = TableSessionManager.get_active_session(request)
        
        if table_session:
            try:
                from restaurants.models import Table
                table = Table.objects.get(id=table_session['table_id'], restaurant=restaurant)
                order.table = table
                order.table_number = table.number  # Backward compatibility
                
                # Incrementar contador de pedidos de la mesa
                table.increment_order_count()
                
                logger.info(f"Mesa {table.number} (ID: {table.id}) asignada al pedido {order.order_number} desde sesión QR")
            except Table.DoesNotExist:
                logger.warning(f"Mesa con ID {table_session['table_id']} no encontrada")
        
        # Si no hay mesa de sesión QR pero sí número de mesa manual
        elif form.cleaned_data.get('table_number'):
            try:
                table = Table.objects.get(
                    number=form.cleaned_data['table_number'], 
                    restaurant=restaurant
                )
                order.table = table
                logger.info(f"Mesa {table.number} asignada manualmente al pedido {order.order_number}")
            except Table.DoesNotExist:
                logger.warning(f"Mesa número {form.cleaned_data['table_number']} no existe")
    
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
    
    # 🆕 NOTIFICAR AL MESERO (compatible con WaiterStaff)
    try:
        from restaurants.waiter_staff_notifications import WaiterStaffNotificationService
        notification = WaiterStaffNotificationService.notify_new_order(order)
        if notification:
            logger.info(f"Notificación enviada a mesero {notification.waiter.full_name} para pedido {order.order_number}")
        else:
            logger.warning(f"No se pudo enviar notificación para pedido {order.order_number}")
    except Exception as e:
        logger.error(f"Error enviando notificación para pedido {order.order_number}: {e}")
    
    return order


def _create_order_item(order, item_data):
    """
    Crear un item de orden a partir de datos del carrito
    🆕 FASE 2: Integrado con estados granulares
    """
    from menu.models import MenuItem, MenuVariant, MenuAddon, MenuModifier
    
    menu_item = MenuItem.objects.get(id=item_data['menu_item_id'])
    
    # Crear el item de orden con estado granular inicial
    order_item = OrderItem.objects.create(
        order=order,
        menu_item=menu_item,
        quantity=item_data['quantity'],
        unit_price=item_data['unit_price'],  # Cambio de base_price a unit_price
        variant_price=item_data.get('variant_price', '0'),
        addons_price=item_data.get('addon_price', '0'),  # Era addons_price, pero en cart es addon_price
        modifiers_price=item_data.get('modifier_price', '0'),  # Era modifiers_price, pero en cart es modifier_price
        total_price=item_data['total_price'],
        special_instructions=item_data.get('special_instructions', ''),
        # 🆕 FASE 2: Estado inicial granular
        status='confirmed'  # Inmediatamente confirmado para preparación
    )
    
    # Agregar variante si existe
    if item_data.get('variant_id'):
        variant = MenuVariant.objects.get(id=item_data['variant_id'])
        order_item.selected_variant = variant
        order_item.save()
    
    # 🆕 FASE 2: Log del nuevo item con estado granular
    logger.info(f"Item creado: {order_item.menu_item.name} - Estado: {order_item.status} - Área: {order_item.responsible_area}")
    
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
        
        # 🎯 DETECTAR SI CLIENTE ESTÁ EN SESIÓN DE MESA
        from restaurants.table_session_manager import TableSessionManager
        table_session = TableSessionManager.get_active_session(self.request)
        
        # Información adicional para la experiencia post-pedido
        show_continue_ordering = False
        table_info = None
        
        if table_session and self.object.table:
            # Cliente está en sesión y pedido es de la misma mesa
            if table_session['table_id'] == self.object.table.id:
                show_continue_ordering = True
                table_info = {
                    'number': self.object.table.number,
                    'name': self.object.table.display_name,
                    'location': self.object.table.location or ''
                }
        
        context.update({
            'restaurant': self.object.restaurant,
            'items': self.object.items.all().prefetch_related(
                'selected_addons', 'selected_modifiers'
            ),
            'show_continue_ordering': show_continue_ordering,  # 🆕 Flag para mostrar opciones adicionales
            'table_info': table_info,                         # 🆕 Info de mesa
            'table_session': table_session,                   # 🆕 Sesión activa
            'page_title': f'Pedido #{self.object.order_number} - {self.object.restaurant.name}',
        })
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
        
        # 🆕 NOTIFICAR AL GARZÓN CUANDO EL PEDIDO ESTÉ LISTO
        if new_status == 'ready':
            try:
                notification = WaiterNotificationService.notify_order_ready(order)
                if notification:
                    logger.info(f"Notificación de pedido listo enviada a garzón {notification.waiter.full_name}")
            except Exception as e:
                logger.error(f"Error enviando notificación de pedido listo: {e}")
        
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


def my_orders(request, tenant_slug):
    """
    Vista para que el cliente vea sus pedidos desde la sesión de mesa
    """
    from restaurants.table_session_manager import TableSessionManager
    
    restaurant = request.restaurant
    table_session = TableSessionManager.get_active_session(request)
    
    # Solo mostrar si hay sesión activa de mesa
    if not table_session:
        messages.warning(request, 'Necesitas estar conectado a una mesa para ver tus pedidos.')
        return redirect(f'/{tenant_slug}/menu/')
    
    try:
        from restaurants.models import Table
        table = Table.objects.get(id=table_session['table_id'])
        
        # Obtener pedidos de esta sesión/mesa del día actual
        from django.utils import timezone
        today = timezone.now().date()
        
        orders = Order.objects.filter(
            restaurant=restaurant,
            table=table,
            created_at__date=today
        ).select_related('table').prefetch_related(
            'items__menu_item',
            'items__selected_variant',
            'items__selected_addons',
            'items__selected_modifiers',
            'status_history'
        ).order_by('-created_at')
        
        # Información de la mesa
        table_info = {
            'number': table.number,
            'name': table.display_name,
            'location': table.location or ''
        }
        
        context = {
            'restaurant': restaurant,
            'orders': orders,
            'table_info': table_info,
            'table_session': table_session,
            'page_title': f'Mis Pedidos - {table.display_name}',
        }
        
        return render(request, 'orders/my_orders.html', context)
        
    except Table.DoesNotExist:
        messages.error(request, 'Mesa no encontrada.')
        return redirect(f'/{tenant_slug}/menu/')
    except Exception as e:
        logger.error(f"Error en my_orders: {e}")
        messages.error(request, 'Error al cargar tus pedidos.')
        return redirect(f'/{tenant_slug}/menu/')


 