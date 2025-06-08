from .cart import Cart


def cart_processor(request):
    """
    Context processor para agregar información del carrito a todas las templates
    """
    cart_data = {
        'cart_total_items': 0,
        'cart_total_price': 0,
    }
    
    try:
        if hasattr(request, 'tenant'):
            cart = Cart(request)
            cart_data = {
                'cart_total_items': len(cart),
                'cart_total_price': cart.get_total_price(),
            }
    except Exception:
        # En caso de error, mantener valores por defecto
        pass
    
    return {
        'cart_info': cart_data,
    } 