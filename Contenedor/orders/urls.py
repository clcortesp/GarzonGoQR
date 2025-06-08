from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    
    # Redirección al carrito
    path('cart/', views.redirect_to_cart, name='cart_redirect'),
    
    # Detalle de orden para cliente
    path('order/<uuid:order_id>/', views.OrderDetailView.as_view(), name='order_detail'),
    
    # Seguimiento de pedido
    path('tracking/<uuid:order_id>/', views.order_tracking, name='order_tracking'),
    
    # Dashboard para restaurante
    path('dashboard/', views.RestaurantOrdersListView.as_view(), name='restaurant_orders'),
    
    # AJAX para actualizar estado
    path('update-status/<uuid:order_id>/', views.update_order_status, name='update_order_status'),
] 