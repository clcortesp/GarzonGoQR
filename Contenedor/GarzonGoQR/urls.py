"""
URL configuration for GarzonGoQR project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from restaurants.views import tenant_info_api
from landing_view import landing_view

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Landing page principal (sin tenant)
    path('', landing_view, name='landing'),
    
    # API global (sin tenant) - solo para testing
    # path('api/tenant-info/', tenant_info_api, name='tenant_info_api'),
    
    # URLs con tenant - DEBE IR AL FINAL
    # Capturamos el tenant_slug pero lo procesamos en el middleware
    path('<slug:tenant_slug>/', include('restaurants.urls')),
]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
