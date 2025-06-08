from django.urls import path
from . import views

app_name = 'menu'

urlpatterns = [

    
    # Menú público
    path('', views.MenuListView.as_view(), name='list'),
    path('item/<slug:item_slug>/', views.MenuItemDetailView.as_view(), name='item_detail'),
    
    # Carrito de compras
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.cart_add, name='cart_add'),
    path('cart/remove/', views.cart_remove, name='cart_remove'),
    path('cart/update/', views.cart_update, name='cart_update'),
    path('cart/clear/', views.cart_clear, name='cart_clear'),
    
    # API endpoints
    path('api/', views.menu_api, name='api_menu'),
] 