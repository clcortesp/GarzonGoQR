from django.urls import path, include, re_path
from . import views
from menu.views import MenuListView

app_name = 'restaurants'

urlpatterns = [

    
    # API para información del tenant (dentro del contexto)
    path('api/tenant-info/', views.tenant_info_api, name='tenant_info_api'),
    
    # Autenticación
    path('login/', views.TenantLoginView.as_view(), name='login'),
    path('logout/', views.TenantLogoutView.as_view(), name='logout'),
    
    # URLs de la app menu (específicas ANTES de la página home)
    path('menu/', include('menu.urls', namespace='menu')),
    

    

    
    # URLs de la app orders
    path('orders/', include('orders.urls', namespace='orders')),
    
    # Dashboard del restaurante (staff) - Redirigir al dashboard funcional de orders
    path('dashboard/', views.DashboardRedirectView.as_view(), name='dashboard'),
    path('dashboard/orders/', views.OrdersRedirectView.as_view(), name='dashboard_orders'),
    path('dashboard/menu/', views.MenuManagementView.as_view(), name='dashboard_menu'),
    
    # QR Code URLs para mesas
    path('table/<uuid:table_uuid>/', views.table_qr_scan, name='table_qr_scan'),
    path('tables/', views.tables_management, name='tables_management'),
    path('tables/create/', views.create_table, name='create_table'),
    path('tables/<int:table_id>/qr/', views.generate_table_qr, name='generate_table_qr'),
    path('tables/<int:table_id>/qr/preview/', views.table_qr_preview, name='table_qr_preview'),
    
    # Configuración del tenant
    path('settings/', views.TenantSettingsView.as_view(), name='settings'),
]

# Página principal del restaurante (SOLO captura URL raíz exacta) - AL FINAL
urlpatterns += [
    path('', views.TenantHomeView.as_view(), name='home'),  # Cambiado de re_path a path
]

 