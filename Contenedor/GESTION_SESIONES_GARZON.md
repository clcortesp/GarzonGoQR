# 🧑‍💼 Gestión de Sesiones de Mesa por Garzones

## 📝 Resumen

Hemos implementado un sistema que permite a los garzones gestionar manualmente las sesiones de sus mesas asignadas, solucionando el problema de sesiones "colgadas" cuando los clientes se van sin finalizar su sesión digital.

## ⏰ Cambios en Tiempos de Sesión

### ⬆️ Nuevos Tiempos Extendidos

- **Duración total de sesión**: `60 minutos` (antes: 30 min)
- **Tiempo de inactividad**: `45 minutos` (antes: 15 min)

### 💡 Justificación

Los tiempos anteriores eran muy restrictivos para la experiencia gastronómica:
- Los clientes pueden estar 30+ minutos comiendo sin interactuar con el menú
- Las conversaciones y la socialización son parte natural de comer
- 15 minutos de inactividad podía cortar sesiones de clientes activos

## 🆕 Nuevas Funcionalidades para Garzones

### 1. 📱 Dashboard Mejorado

**Ubicación**: `/{tenant_slug}/waiter/`

**Nuevas características**:
- **Estado visual de mesas**: Cada mesa muestra si tiene sesión activa o está libre
- **Badges informativos**: 
  - 🟡 "Pedidos" - Mesa con órdenes pendientes
  - 🔵 "Sesión Activa" - Cliente conectado al menú digital
  - ⚫ "Libre" - Mesa disponible para nuevos clientes
- **Información de sesión**: Tiempo transcurrido desde que el cliente se conectó
- **Botón "Actualizar Estado"**: Refresh manual del estado de todas las mesas

### 2. 🔄 Control de Sesiones

**Botones por mesa**:
- **"Finalizar"** (sesión activa): Termina la sesión del cliente
- **"Preparar"** (mesa libre): Marca mesa como lista para nuevos clientes
- **"Ver"**: Acceso a detalles de la mesa

### 3. 🎯 Finalización Manual de Sesiones

**Proceso**:
1. Garzón observa que clientes han terminado y se van
2. Hace clic en "Finalizar" en la mesa correspondiente
3. Confirma la acción (con advertencia sobre desconexión)
4. Sistema registra la finalización y libera la mesa

**Seguridad**:
- Solo el garzón asignado puede finalizar sesiones de sus mesas
- Se registra quién y cuándo finalizó cada sesión
- Se crea log de auditoría automático

## 🔧 APIs Implementadas

### 1. Finalizar Sesión de Mesa
```
POST /{tenant_slug}/waiter/end-table-session/
Content-Type: application/json

{
    "table_id": 123,
    "reason": "Clientes finalizaron comida"
}
```

### 2. Estado de Sesiones
```
GET /{tenant_slug}/waiter/table-sessions-status/

Response:
{
    "success": true,
    "tables": [
        {
            "id": 123,
            "number": 5,
            "has_active_session": true,
            "session_info": {
                "scan_time": "2024-01-15T14:30:00Z",
                "time_ago": 25.5,
                "estimated_expires": "2024-01-15T15:30:00Z"
            }
        }
    ]
}
```

## 🎨 Mejoras en UI/UX

### Visual
- **Cards rediseñadas**: Layout más limpio con información estructurada
- **Sistema de badges**: Código de colores intuitivo para estados
- **Botones contextuales**: Acciones cambian según estado de la mesa
- **Notificaciones toast**: Feedback inmediato de acciones

### Interactividad
- **Confirmaciones inteligentes**: Aviso antes de desconectar clientes
- **Auto-refresh optimizado**: Actualización cada 45s (menos intrusivo)
- **Estados en tiempo real**: UI se actualiza inmediatamente tras acciones

## 📋 Flujo de Trabajo Típico

### 🌅 Inicio de Turno
1. Garzón accede a su dashboard
2. Revisa estado de todas sus mesas asignadas
3. Ve qué mesas tienen sesiones activas de turnos anteriores

### 🍽️ Durante el Servicio
1. **Clientes llegan**: Escanean QR → Mesa muestra "Sesión Activa"
2. **Garzón atiende**: Ve estado actualizado en dashboard
3. **Clientes piden**: Órdenes aparecen con badge "Pedidos"
4. **Clientes terminan**: Garzón observa que se van físicamente

### 🧹 Liberación de Mesa
1. **Garzón confirma**: Clientes han terminado y se van
2. **Clic "Finalizar"**: Termina sesión digital inmediatamente
3. **Mesa preparada**: Badge cambia a "Libre", botón "Preparar" disponible
4. **Nuevos clientes**: Mesa lista para próximo escaneo QR

## 🔐 Seguridad y Auditoría

### Controles de Acceso
- Solo garzones pueden finalizar sesiones de sus mesas asignadas
- Verificación de autoridad antes de cada acción
- Logs detallados de todas las finalizaciones

### Registro de Auditoría
```python
TableScanLog.objects.create(
    table=table,
    scanned_at=timezone.now(),
    ip_address="WAITER_CLEANUP",
    user_agent="Finalizada por garzón: Juan Pérez - Clientes finalizaron comida",
    resulted_in_order=False
)
```

### Notificaciones Automáticas
- Garzón recibe confirmación de sesión finalizada
- Registro en historial de notificaciones
- Timestamp de acción para seguimiento

## 🚀 Beneficios del Sistema

### Para el Restaurante
- **Optimización de mesas**: Rotación más eficiente
- **Mejor experiencia**: Mesas siempre listas para nuevos clientes
- **Control operativo**: Garzones gestionan activamente sus secciones

### Para los Garzones
- **Visibilidad total**: Estado claro de todas sus mesas
- **Control directo**: Pueden liberar mesas cuando es necesario
- **Herramientas profesionales**: Dashboard diseñado para su workflow

### Para los Clientes
- **Sesiones más largas**: Tiempo suficiente para disfrutar la comida
- **Sin interrupciones**: No se desconectan mientras están comiendo
- **Transiciones suaves**: Mesa lista inmediatamente para próximo grupo

## 📈 Configuración Avanzada

### Ajustar Tiempos de Sesión

En `settings.py`:
```python
# Duración total de sesión (minutos)
TABLE_SESSION_DURATION = 60

# Tiempo máximo sin actividad (minutos)  
TABLE_INACTIVITY_TIMEOUT = 45
```

### Personalizar por Restaurante
```python
# En el modelo Restaurant, se pueden agregar campos específicos
class Restaurant(models.Model):
    # ... campos existentes ...
    session_duration_minutes = models.IntegerField(default=60)
    inactivity_timeout_minutes = models.IntegerField(default=45)
```

## 🎯 Próximos Pasos Sugeridos

1. **Analytics de sesiones**: Métricas de duración promedio y rotación
2. **Alertas automáticas**: Notificar cuando sesión lleva mucho tiempo activa
3. **Integración con POS**: Sincronizar finalización con cierre de cuenta
4. **App móvil**: Dashboard nativo para garzones en teléfonos/tablets
5. **Gestión de cola**: Sistema de lista de espera cuando todas las mesas están ocupadas

## 📞 Soporte

Para dudas o problemas con el sistema de gestión de sesiones:
- Revisar logs en el panel de administración
- Verificar configuración de tiempos en settings
- Consultar historial de notificaciones del garzón

---

💡 **Tip**: Este sistema funciona mejor cuando los garzones lo usan activamente. El entrenamiento del personal es clave para maximizar los beneficios operativos. 