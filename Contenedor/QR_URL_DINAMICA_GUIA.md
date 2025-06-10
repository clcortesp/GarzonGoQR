# 📱 Sistema de URLs Dinámicas para Códigos QR

## 🎯 **Problema Solucionado**

**Antes**: URL base estática codificada
```python
# ❌ Problema: URL hardcodeada
base_url = "http://localhost:8000"  # No funciona en producción
```

**Ahora**: Sistema inteligente de detección automática con múltiples fallbacks
```python
# ✅ Solución: Detección dinámica
qr_url = table.get_full_qr_url(request)  # Se adapta automáticamente
```

## 🏆 **Orden de Prioridad para URLs**

### **1. 🚀 Detección Automática (Recomendado)**
**Cómo funciona**: Usa `request.build_absolute_uri()`
```python
# Detecta automáticamente:
# - Protocolo: http/https
# - Dominio: localhost, miapp.com, etc.
# - Puerto: 8000, 80, 443, etc.

request.build_absolute_uri('/mi-restaurant/table/uuid/')
# → "https://miapp.com/mi-restaurant/table/uuid/"
```

**Ventajas**:
- ✅ **Automático**: No requiere configuración
- ✅ **Preciso**: Detecta el entorno real
- ✅ **Robusto**: Funciona en desarrollo y producción

### **2. 🏢 Dominio Personalizado del Tenant**
**Cómo configurar**: En el admin de Django
```python
# Base de datos: Tenant.domain = "mirestaurante.com"
tenant.domain = "mirestaurante.com"
# → "https://mirestaurante.com/mi-restaurant/table/uuid/"
```

**Usar para**:
- 🎯 Restaurantes con dominio propio
- 🔗 URLs branded personalizadas
- 📱 QRs con identidad corporativa

### **3. ⚙️ Configuración Global en Settings**
**Cómo configurar**: En `settings.py`
```python
# settings.py
QR_BASE_URL = "https://miapp.com"
# → "https://miapp.com/mi-restaurant/table/uuid/"
```

**Usar para**:
- 🌍 Configuración global de la app
- 🔧 Control centralizado de URLs
- 📊 Consistency across tenants

### **4. 🔄 Fallback Automático**
**Cómo funciona**: Basado en `DEBUG` setting
```python
# Si DEBUG=True (desarrollo)
"http://localhost:8000/mi-restaurant/table/uuid/"

# Si DEBUG=False (producción)  
"https://midominio.com/mi-restaurant/table/uuid/"
```

## 🔧 **Implementación en el Código**

### **Método Principal en el Modelo**
```python
def get_full_qr_url(self, request=None):
    """Obtener URL completa del QR con diferentes estrategias"""
    
    # 1. Request disponible (MEJOR)
    if request:
        return request.build_absolute_uri(self.qr_url)
    
    # 2. Dominio del tenant
    if self.restaurant.tenant.domain:
        protocol = 'https' if settings.USE_HTTPS else 'http'
        return f"{protocol}://{self.restaurant.tenant.domain}{self.qr_url}"
    
    # 3. Configuración en settings
    if settings.QR_BASE_URL:
        return f"{settings.QR_BASE_URL.rstrip('/')}{self.qr_url}"
    
    # 4. Fallback automático
    default = "http://localhost:8000" if settings.DEBUG else "https://midominio.com"
    return f"{default}{self.qr_url}"
```

### **Uso en Vistas**
```python
# Antes
qr.add_data(table.full_qr_url)  # ❌ URL estática

# Ahora  
qr_url = table.get_full_qr_url(request)  # ✅ URL dinámica
qr.add_data(qr_url)
```

## ⚙️ **Configuración por Entorno**

### **🔧 Desarrollo Local**
```python
# settings/development.py
DEBUG = True
QR_BASE_URL = "http://localhost:8000"
USE_HTTPS = False
```

### **🧪 Staging**
```python
# settings/staging.py
DEBUG = False
QR_BASE_URL = "https://staging.miapp.com"
USE_HTTPS = True
```

### **🚀 Producción**
```python
# settings/production.py
DEBUG = False
QR_BASE_URL = "https://miapp.com"
USE_HTTPS = True

# Variable de entorno
DJANGO_ENV = 'production'
```

## 🏢 **Configuración de Dominios Personalizados**

### **1. En la Base de Datos (Admin)**
```python
# Modelo Tenant actualizado
class Tenant(models.Model):
    domain = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="Dominio personalizado",
        help_text="ej: mirestaurante.com"
    )
```

### **2. Configuración en el Admin**
```
1. Ir a: /{tenant_slug}/admin/
2. Panel: "Configuración de QR"
3. Campo: "Dominio personalizado"
4. Ejemplo: "mirestaurante.com"
```

### **3. Múltiples Dominios (Avanzado)**
```python
# settings.py
TENANT_DOMAINS = {
    'restaurant-1': 'restaurant1.com',
    'restaurant-2': 'restaurant2.com',
}
```

## 📊 **Dashboard de Configuración QR**

El admin dashboard muestra:
```
📱 Estado Actual de QR:
✅ Método de detección: Automático desde request
🌐 URL de ejemplo: https://miapp.com/tenant/table/uuid/
🔧 Dominio personalizado: mirestaurante.com
```

## 🎯 **Mejores Prácticas**

### **✅ Recomendaciones**
1. **Usar detección automática** cuando sea posible
2. **Configurar dominio personalizado** para branding
3. **Testear QRs** en diferentes entornos
4. **Validar URLs** antes de generar códigos

### **⚠️ Consideraciones**
- **HTTPS en producción**: Usar siempre SSL/TLS
- **Dominios válidos**: Verificar que el dominio responda
- **Cache de QR**: Los QRs generados reflejan la URL del momento
- **Backup URLs**: Tener fallbacks configurados

## 🔄 **Migración de URLs Estáticas**

### **Pasos para Migrar**
1. ✅ **Actualizar modelo**: Agregar campo `domain` a `Tenant`
2. ✅ **Ejecutar migración**: `python manage.py migrate`
3. ✅ **Configurar entornos**: Agregar settings por entorno
4. ✅ **Testear QRs**: Verificar URLs generadas
5. ✅ **Regenerar QRs**: Opcional, para URLs actualizadas

### **Compatibilidad**
- **QRs existentes**: Siguen funcionando (URLs no cambian)
- **Nuevos QRs**: Usan el sistema dinámico
- **Regeneración**: Solo necesaria si quieres URLs actualizadas

## 📱 **Ejemplos de URLs Generadas**

### **Desarrollo**
```
Detección automática:
http://localhost:8000/mi-restaurant/table/abc123/

Configuración manual:
http://localhost:8000/mi-restaurant/table/abc123/
```

### **Producción**
```
Detección automática:
https://miapp.com/mi-restaurant/table/abc123/

Dominio personalizado:
https://mirestaurante.com/mi-restaurant/table/abc123/

Multi-tenant:
https://cliente1.com/restaurant/table/abc123/
https://cliente2.com/restaurant/table/abc123/
```

## 🛠️ **Troubleshooting**

### **🔍 URLs Incorrectas**
```python
# Debug: Ver qué método se está usando
table = Table.objects.first()
url = table.get_full_qr_url(request)
print(f"QR URL: {url}")
```

### **🌐 Dominio No Funciona**
1. Verificar DNS del dominio
2. Confirmar SSL/TLS configurado
3. Testear acceso directo al dominio

### **⚙️ Settings No Se Aplican**
1. Verificar `QR_BASE_URL` en settings
2. Confirmar entorno correcto (`DJANGO_ENV`)
3. Reiniciar servidor Django

## 🎉 **Beneficios del Sistema**

### **🚀 Para Desarrollo**
- **Setup inmediato**: Funciona sin configuración
- **Testing fácil**: URLs correctas automáticamente
- **Debug simple**: Ver URLs generadas fácilmente

### **🏢 Para Producción**
- **Escalabilidad**: Múltiples dominios soportados
- **Branding**: URLs personalizadas por cliente
- **Flexibilidad**: Configuración por entorno

### **👨‍💼 Para Administradores**
- **Control total**: Configurar dominios desde admin
- **Visibilidad**: Ver configuración actual en dashboard
- **Simplicidad**: Un click para descargar QR correcto

---

🎯 **El sistema ahora es 100% dinámico y production-ready!** 🚀 