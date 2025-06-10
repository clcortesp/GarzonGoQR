# 🎯 CONFIGURACIÓN DE URLS BASE PARA QR CODES
# Agregar estas configuraciones a tu settings.py

# ============================================================================
# CONFIGURACIÓN DE QR CODES
# ============================================================================

# 🔧 URL base para códigos QR (opcional)
# Si no se especifica, se usará detección automática desde el request
QR_BASE_URL = None  # Ejemplo: "https://mirestaurante.com"

# 🔒 Forzar HTTPS en producción
USE_HTTPS = True  # En producción: True, en desarrollo: False

# 🌍 Configuración por entorno
import os
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development')

if ENVIRONMENT == 'production':
    # 🚀 PRODUCCIÓN
    QR_BASE_URL = "https://mirestaurante.com"
    USE_HTTPS = True
    
elif ENVIRONMENT == 'staging':
    # 🧪 STAGING/PRUEBAS
    QR_BASE_URL = "https://staging.mirestaurante.com"
    USE_HTTPS = True
    
elif ENVIRONMENT == 'development':
    # 💻 DESARROLLO
    QR_BASE_URL = "http://localhost:8000"
    USE_HTTPS = False

# ============================================================================
# EJEMPLO DE USO EN DIFERENTES ESCENARIOS
# ============================================================================

"""
📱 ORDEN DE PRIORIDAD para generar URLs de QR:

1. 🏆 REQUEST DISPONIBLE (Recomendado)
   - Detecta automáticamente: protocolo, dominio, puerto
   - Ejemplo: request.build_absolute_uri('/mi-restaurant/table/uuid/')
   - Resultado: "https://midominio.com/mi-restaurant/table/uuid/"

2. 🏢 DOMINIO DEL TENANT (Base de datos)
   - Se configura en el admin: Tenant.domain = "mirestaurante.com"
   - Usa configuración USE_HTTPS para protocolo
   - Resultado: "https://mirestaurante.com/mi-restaurant/table/uuid/"

3. ⚙️ SETTINGS QR_BASE_URL
   - Configuración global en settings.py
   - Ejemplo: QR_BASE_URL = "https://miapp.com"
   - Resultado: "https://miapp.com/mi-restaurant/table/uuid/"

4. 🔄 FALLBACK AUTOMÁTICO
   - Si DEBUG=True: "http://localhost:8000"
   - Si DEBUG=False: "https://midominio.com"
   - Resultado: URL por defecto según entorno
"""

# ============================================================================
# CONFIGURACIÓN AVANZADA DE MULTI-DOMINIO
# ============================================================================

# 🌐 Para restaurantes con dominios personalizados
TENANT_DOMAINS = {
    'mi-restaurant': 'mirestaurante.com',
    'otro-restaurant': 'otrorestaurante.com',
}

# 📧 Configuración de email para notificaciones de QR
QR_NOTIFICATION_EMAIL = {
    'from_email': 'noreply@miapp.com',
    'subject_prefix': '[QR System] ',
}

# 📊 Analytics de QR codes
QR_ANALYTICS = {
    'track_scans': True,
    'track_location': True,  # Recopilar IP para estadísticas
    'retention_days': 90,    # Mantener logs por 90 días
} 