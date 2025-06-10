from django.urls import path, include, re_path
from . import views
from . import waiter_views
from . import admin_views
from . import session_api_views
from . import kitchen_views
from . import bar_views
from menu.views import MenuListView

app_name = 'restaurants'

urlpatterns = [

    
    # API para información del tenant (dentro del contexto)
    path('api/tenant-info/', views.tenant_info_api, name='tenant_info_api'),
    
    # Autenticación
    path('staff/login/', views.StaffLoginPageView.as_view(), name='staff_login'),
    path('login/', views.TenantLoginView.as_view(), name='login'),
    path('logout/', views.TenantLogoutView.as_view(), name='logout'),
    path('logout-simple/', views.simple_logout_view, name='logout_simple'),
    path('test-logout/', views.test_logout_view, name='test_logout'),
    path('test-links/', views.test_links_view, name='test_links'),
    
    # URLs de la app menu (específicas ANTES de la página home)
    path('menu/', include('menu.urls', namespace='menu')),
    

    

    
    # URLs de la app orders
    path('orders/', include('orders.urls', namespace='orders')),
    
    # Dashboard del restaurante (staff) - Redirigir al dashboard funcional de orders
    path('dashboard/', views.DashboardRedirectView.as_view(), name='dashboard'),
    path('dashboard/orders/', views.OrdersRedirectView.as_view(), name='dashboard_orders'),
    path('dashboard/menu/', views.MenuManagementView.as_view(), name='dashboard_menu'),
    
    # 🏢 PANEL DE ADMINISTRACIÓN DEL RESTAURANTE
    path('admin/', admin_views.RestaurantAdminDashboard.as_view(), name='admin_dashboard'),
    path('admin/logout/', admin_views.admin_logout_view, name='admin_logout'),
    
    # Gestión de Menú
    path('admin/menu/', admin_views.MenuManagementView.as_view(), name='admin_menu'),
    path('admin/menu/create/', admin_views.create_menu_item, name='admin_menu_create'),
    path('admin/menu/<uuid:item_id>/edit/', admin_views.edit_menu_item, name='admin_menu_edit'),
    path('admin/menu/<uuid:item_id>/delete/', admin_views.delete_menu_item, name='admin_menu_delete'),
    
    # Gestión de Garzones (Sistema Antiguo)
    path('admin/waiters/', admin_views.WaitersManagementView.as_view(), name='admin_waiters'),
    path('admin/waiters/create/', admin_views.create_waiter, name='admin_waiters_create'),
    path('admin/waiters/<int:waiter_id>/edit/', admin_views.edit_waiter, name='admin_waiters_edit'),
    path('admin/waiters/<int:waiter_id>/delete/', admin_views.delete_waiter, name='admin_waiters_delete'),
    
    # Gestión de Personal de Cocina
    path('admin/kitchen-staff/', admin_views.KitchenStaffManagementView.as_view(), name='admin_kitchen_staff'),
    path('admin/kitchen-staff/create/', admin_views.create_kitchen_staff, name='admin_kitchen_staff_create'),
    path('admin/kitchen-staff/<int:staff_id>/edit/', admin_views.edit_kitchen_staff, name='admin_kitchen_staff_edit'),
    path('admin/kitchen-staff/<int:staff_id>/delete/', admin_views.delete_kitchen_staff, name='admin_kitchen_staff_delete'),
    
    # Gestión de Personal de Bar
    path('admin/bar-staff/', admin_views.BarStaffManagementView.as_view(), name='admin_bar_staff'),
    path('admin/bar-staff/create/', admin_views.create_bar_staff, name='admin_bar_staff_create'),
    path('admin/bar-staff/<int:staff_id>/edit/', admin_views.edit_bar_staff, name='admin_bar_staff_edit'),
    path('admin/bar-staff/<int:staff_id>/delete/', admin_views.delete_bar_staff, name='admin_bar_staff_delete'),
    
    # Gestión de Meseros (Nuevo Sistema)
    path('admin/waiter-staff/', admin_views.WaiterStaffManagementView.as_view(), name='admin_waiter_staff'),
    path('admin/waiter-staff/create/', admin_views.create_waiter_staff, name='admin_waiter_staff_create'),
    path('admin/waiter-staff/<int:staff_id>/edit/', admin_views.edit_waiter_staff, name='admin_waiter_staff_edit'),
    path('admin/waiter-staff/<int:staff_id>/delete/', admin_views.delete_waiter_staff, name='admin_waiter_staff_delete'),
    
    # Gestión de Mesas
    path('admin/tables/', admin_views.TablesManagementView.as_view(), name='admin_tables'),
    path('admin/tables/create/', admin_views.create_table_admin, name='admin_tables_create'),
    path('admin/tables/<int:table_id>/edit/', admin_views.edit_table_admin, name='admin_tables_edit'),
    path('admin/tables/<int:table_id>/delete/', admin_views.delete_table, name='admin_tables_delete'),
    path('admin/tables/<int:table_id>/qr/preview/', admin_views.table_qr_preview, name='admin_tables_qr_preview'),
    path('admin/tables/<int:table_id>/qr/download/', admin_views.table_qr_download, name='admin_tables_qr_download'),
    
    # Reportes y Analytics
    path('admin/reports/sales/', admin_views.SalesReportView.as_view(), name='admin_sales_report'),
    
    # 🍳 SISTEMA DE COCINA
    path('kitchen/', kitchen_views.kitchen_dashboard, name='kitchen_dashboard'),
    path('kitchen/orders/', kitchen_views.kitchen_orders_list, name='kitchen_orders_list'),
    path('kitchen/item/<int:item_id>/status/', kitchen_views.update_item_status, name='kitchen_update_item_status'),
    path('kitchen/item/<int:item_id>/prep-time/', kitchen_views.update_prep_time, name='kitchen_update_prep_time'),
    path('kitchen/status/update/', kitchen_views.update_kitchen_status, name='update_kitchen_status'),
    
    # 🍸 SISTEMA DE BAR
    path('bar/', bar_views.bar_dashboard, name='bar_dashboard'),
    path('bar/orders/', bar_views.bar_orders_list, name='bar_orders_list'),
    path('bar/drink/<int:item_id>/status/', bar_views.update_drink_status, name='bar_update_drink_status'),
    path('bar/status/update/', bar_views.update_bar_status, name='update_bar_status'),
    path('bar/inventory/', bar_views.bar_inventory_status, name='bar_inventory_status'),
    
    # 🍽️ SISTEMA DE GARZONES
    path('waiter/', waiter_views.waiter_dashboard, name='waiter_dashboard'),
    path('waiter/notifications/', waiter_views.waiter_notifications, name='waiter_notifications'),
    path('waiter/notifications/<int:notification_id>/read/', waiter_views.mark_notification_read, name='mark_notification_read'),
    path('waiter/notifications/<int:notification_id>/respond/', waiter_views.mark_notification_responded, name='mark_notification_responded'),
    path('waiter/notifications/mark-all-read/', waiter_views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('waiter/tables/', waiter_views.waiter_tables, name='waiter_tables'),
    path('waiter/status/update/', waiter_views.update_waiter_status, name='update_waiter_status'),
    path('waiter/stats/', waiter_views.waiter_stats_api, name='waiter_stats_api'),
    path('waiter/end-table-session/', waiter_views.waiter_end_table_session, name='waiter_end_table_session'),
    path('waiter/table-sessions-status/', waiter_views.waiter_table_sessions_status, name='waiter_table_sessions_status'),
    
    # QR Code URLs para mesas
    path('table/<uuid:table_uuid>/', views.table_qr_scan, name='table_qr_scan'),
    path('tables/', views.tables_management, name='tables_management'),
    path('tables/create/', views.create_table, name='create_table'),
    path('tables/<int:table_id>/qr/', views.generate_table_qr, name='generate_table_qr'),
    path('tables/<int:table_id>/qr/preview/', views.table_qr_preview, name='table_qr_preview'),
    
    # Solicitar asistencia desde mesa
    path('table/<int:table_id>/request-assistance/', waiter_views.request_customer_assistance, name='request_customer_assistance'),
    
    # 🚨 Página especial para sesión cerrada por garzón
    path('session-closed/', views.session_closed_by_waiter, name='session_closed_by_waiter'),
    
    # 🔐 APIS DE SESIÓN DE MESA
    path('api/extend-session/', session_api_views.ExtendSessionAPI.as_view(), name='extend_session_api'),
    path('api/end-session/', session_api_views.EndSessionAPI.as_view(), name='end_session_api'),
    path('api/session-status/', session_api_views.SessionStatusAPI.as_view(), name='session_status_api'),
    
    # Configuración del tenant
    path('settings/', views.TenantSettingsView.as_view(), name='settings'),
]

# Página principal del restaurante (SOLO captura URL raíz exacta) - AL FINAL
urlpatterns += [
    path('', views.TenantHomeView.as_view(), name='home'),  # Cambiado de re_path a path
]

 