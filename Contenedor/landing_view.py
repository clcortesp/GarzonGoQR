from django.shortcuts import render
from django.views.generic import TemplateView
from restaurants.models import Tenant, Restaurant

def landing_view(request):
    """
    Página de inicio principal de GarzónGo QR
    Muestra los restaurantes disponibles
    """
    # Obtener todos los restaurantes activos
    restaurants = Restaurant.objects.filter(
        is_active=True,
        tenant__status='ACTIVE'
    ).select_related('tenant')
    
    context = {
        'title': 'GarzónGo QR - Sistema de Pedidos Digital',
        'restaurants': restaurants,
    }
    
    return render(request, 'landing.html', context)


class SmartLandingView(TemplateView):
    """
    Vista inteligente para landing page que detecta si hay un solo tenant
    """
    template_name = 'landing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener todos los restaurantes activos
        restaurants = Restaurant.objects.filter(
            is_active=True,
            tenant__status='ACTIVE'
        ).select_related('tenant')
        
        context.update({
            'title': 'GarzónGo QR - Sistema de Pedidos Digital',
            'restaurants': restaurants,
        })
        
        return context 