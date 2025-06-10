# 🔐 Sistema de Sesiones de Mesa - Guía Completa

## 🚨 Problema Original
- Cliente escanea QR, se va del restaurante, pero el navegador sigue abierto
- Otra persona podría seguir pidiendo en esa mesa
- No hay control de tiempo ni seguridad en las sesiones

## ✅ Solución Implementada: Sistema de Sesiones Seguras

### **Características Principales:**

1. **⏰ Expiración Automática**
   - Sesión dura 30 minutos por defecto (configurable)
   - Auto-expiración después de 15 minutos sin actividad
   - Timer visual en tiempo real para el usuario

2. **🔑 Token Único por Sesión**
   - Cada escaneo genera un UUID único
   - Imposible de duplicar o falsificar
   - Se almacena en caché Redis + sesión del navegador

3. **📱 Experiencia de Usuario Mejorada**
   - Indicador visual de sesión activa
   - Botón para extender sesión cuando está expirando
   - Modal automático cuando expira
   - Posibilidad de finalizar sesión manualmente

4. **🛡️ Seguridad Robusta**
   - Validación por IP y User Agent
   - Verificación de que la mesa sigue activa
   - Invalidación automática si se detectan problemas

## 📋 Cómo Funciona

### **1. Escaneo de QR:**
```python
# Al escanear QR:
session_token, session_data = TableSessionManager.create_table_session(table, request)
# Genera: UUID único + datos en caché + registro en DB
```

### **2. Validación Continua:**
```python
# En cada request:
session_data = TableSessionManager.get_active_session(request)
# Verifica: token válido + tiempo no expirado + mesa activa
```

### **3. Auto-Expiración:**
```javascript
// En el frontend:
setInterval(updateSessionTimer, 1000); // Timer visual cada segundo
// Si expira: Modal + redirect automático
```

## 🎛️ Configuración

### **En settings.py:**
```python
# Duración de sesión (minutos)
TABLE_SESSION_DURATION = 30  # 30 minutos por defecto

# Timeout de inactividad (minutos)  
TABLE_INACTIVITY_TIMEOUT = 15  # 15 minutos sin actividad
```

### **Configuración de Cache:**
```python
# Requiere Redis o Memcached
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

## 🔌 Integración en el Código

### **1. En las vistas que requieren mesa:**
```python
from .session_api_views import require_table_session

@require_table_session
def mi_vista(request, tenant_slug):
    # request.table_session contiene los datos de la mesa
    table_id = request.table_session['table_id']
    # ... resto de la vista
```

### **2. En templates:**
```django
<!-- Incluir información de sesión -->
{% include 'restaurants/includes/table_session_info.html' %}

<!-- Verificar si hay sesión activa -->
{% if table_session_info %}
    <p>Conectado a {{ table_session_info.table_name }}</p>
{% endif %}
```

### **3. En vistas basadas en clases:**
```python
from .session_api_views import add_session_context_to_view

@add_session_context_to_view
class MiVista(TemplateView):
    # Automáticamente agrega table_session_info al contexto
    pass
```

## 🔄 Flujo Completo

### **Escenario Normal:**
1. **Cliente escanea QR** → Sesión creada (30 min)
2. **Cliente navega/pide** → Actividad actualizada
3. **Cliente termina** → Sesión expira naturalmente
4. **Nuevo cliente escanea** → Nueva sesión limpia

### **Escenario Problemático (Solucionado):**
1. **Cliente escanea QR** → Sesión creada
2. **Cliente se va** → Navegador abierto
3. **15 min sin actividad** → Sesión auto-expira
4. **Otra persona intenta usar** → Mensaje "Sesión expirada"
5. **Debe escanear QR nuevamente** → Nueva sesión segura

## 🚀 APIs Disponibles

### **Extender Sesión:**
```javascript
POST /pizzeria-luigi/api/extend-session/
// Extiende 30 minutos más
```

### **Finalizar Sesión:**
```javascript  
POST /pizzeria-luigi/api/end-session/
// Termina sesión inmediatamente
```

### **Estado de Sesión:**
```javascript
GET /pizzeria-luigi/api/session-status/
// Obtiene información completa de la sesión
```

## 💡 Opciones Adicionales de Seguridad

### **Opción A: QR Dinámicos (Más Seguro)**
- Regenerar QR cada X horas
- QR con timestamp incorporado
- Complejidad: Media

### **Opción B: Códigos de Mesa (Alternativo)**
- Cliente ingresa código numérico
- Códigos cambian periódicamente
- Complejidad: Baja

### **Opción C: Geolocalización (Avanzado)**
- Verificar ubicación del cliente
- Solo funciona dentro del restaurante
- Complejidad: Alta

### **Opción D: Bluetooth Beacons (Futuro)**
- Detectar proximidad física
- Tecnología más avanzada
- Complejidad: Muy Alta

## 🔧 Mantenimiento y Monitoreo

### **Logs Disponibles:**
- `TableScanLog`: Registro de todos los escaneos
- Cache Redis: Sesiones activas en tiempo real
- Django Sessions: Backup de sesiones

### **Métricas Importantes:**
- Tiempo promedio de sesión
- Tasa de renovación de sesiones
- Sesiones expiradas vs completadas
- Problemas de validación

### **Limpieza Automática:**
- Cache expira automáticamente
- Logs antiguos pueden archivarse
- Sesiones inactivas se invalidan solas

## ⚡ Ventajas del Sistema Implementado

1. **Seguridad**: Tokens únicos + validación estricta
2. **UX**: Usuario siempre informado del estado
3. **Flexibilidad**: Configurable según necesidades
4. **Escalabilidad**: Cache distribuido con Redis
5. **Monitoreo**: Logs completos de actividad
6. **Mantenimiento**: Auto-limpieza de datos obsoletos

## 🎯 Recomendación Final

**El sistema implementado es la solución ideal porque:**
- Resuelve el problema de seguridad original
- Mantiene excelente experiencia de usuario
- Es técnicamente sólido y escalable
- No requiere cambios complejos en el frontend
- Es configurable para diferentes restaurantes

**NO se recomienda cambiar QR dinámicos** porque añadiría complejidad innecesaria sin beneficios significativos adicionales. 