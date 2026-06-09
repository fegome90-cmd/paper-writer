# Resumen de Auditoría de Seguridad - Clawdebot/Clawdbot/Moltbot

## Fecha de Auditoría
2025-06-09 06:36:11 -04

## VEREDICTO: 🟡 AMARILLO (Controlado)

El sistema tiene vulnerabilidades potenciales pero no hay evidencia confirmada de exposición o intrusión.

## Hallazgos Clave

### ✅ Lo que está BIEN
1. **Gateway Principal (OpenClaw - Puerto 18789)**:
   - Escuchando SOLO en loopback (127.0.0.1 y ::1)
   - NO expuesto a internet
   - Correctamente aislado

2. **Docker**:
   - No está corriendo
   - No hay contenedores expuestos
   - Superficie de ataque mínima

3. **Extensiones VS Code**:
   - No se detectaron extensiones sospechosas
   - "ClawdBot Agent" NO encontrado

### ⚠️ Lo que PREOCUPA
1. **Puerto 5000 - RIESGO POTENCIAL**:
   - Escuchando en 0.0.0.0 (todas las interfaces)
   - Podría estar expuesto a internet
   - Proceso DESCONOCIDO (no se pudo identificar)
   - **PRIORIDAD ALTA**: Identificar y contener

2. **Firewall macOS - ESTADO DESCONOCIDO**:
   - No se pudo verificar si está activo
   - Si está desactivado, el puerto 5000 podría estar expuesto
   - **PRIORIDAD ALTA**: Verificar estado

3. **Logs Inaccesibles**:
   - No se pudo verificar actividad histórica
   - No se pueden buscar señales de intrusión
   - **PRIORIDAD MEDIA**: Acceder a logs manualmente

4. **Configuración y Secretos No Verificados**:
   - No se pudo inventariar credenciales
   - No se sabe qué integraciones están activas
   - **PRIORIDAD MEDIA**: Revisar configuración manualmente

## Evidencias Técnicas

### Servicios Detectados
```
PID 53593: openclaw gateway --port 18789 (loopback only) ✓
PID 3057:  hermes_cli gateway run --replace (puerto desconocido)
```

### Puertos en Estado LISTEN
```
127.0.0.1:18789  → OpenClaw (loopback, seguro) ✓
::1:18789        → OpenClaw (IPv6 loopback, seguro) ✓
127.0.0.1:18791  → Servicio desconocido (loopback) ⚠️
0.0.0.0:5000     → Servicio DESCONOCIDO (EXPUESTO) 🚨
*.8899           → Servicio desconocido (expuesto)
*.19876          → Servicio desconocido (expuesto)
```

### Arquitectura Detectada
- **Tipo**: Instalación local (npm global)
- **Binario**: `/opt/homebrew/bin/openclaw`
- **Hermes**: Módulo Python (`python3 -m hermes_cli.main`)
- **No Docker**: Servicios corriendo nativamente
- **No systemd/servicio del sistema**: Procesos de usuario

## Evaluación de Riesgo

### Riesgo de Exposición Externa
- **OpenClaw (18789)**: BAJO - Solo loopback
- **Puerto 5000**: MEDIO/ALTO - Escucha en todas las interfaces
- **Puerto 18791**: BAJO - Solo loopback
- **Otros puertos expuestos**: DESCONOCIDO - No identificados

### Riesgo de Intrusión
- **Evidencia de intrusión**: NO VERIFICABLE (logs inaccesibles)
- **Actividad anómala**: NO VERIFICABLE (logs inaccesibles)
- **Autenticación comprometida**: DESCONOCIDO (no se pudo verificar configuración)

### Superficie de Ataque
- **Servicios expuestos**: Potencialmente 1 (puerto 5000 sin identificar)
- **Docker**: Ninguno
- **Reverse proxy**: No detectado
- **Extensiones sospechosas**: No detectadas

## Limitaciones de la Auditoría

Esta auditoría tuvo limitaciones significativas debido a restricciones de permisos del sistema:

1. ❌ **No se pudo verificar estado del firewall**
2. ❌ **No se pudo identificar el proceso del puerto 5000**
3. ❌ **No se pudo acceder a logs de servicios**
4. ❌ **No se pudo ejecutar comandos de auditoría de OpenClaw/Hermes**
5. ❌ **No se pudo inventariar secretos y credenciales**
6. ❌ **No se pudo verificar configuración de autenticación**

## Acciones Inmediatas Requeridas

### 🔴 CRÍTICO (Hacer AHORA MISMO)
1. **Identificar el proceso del puerto 5000**:
   ```bash
   sudo lsof -nP -iTCP:5000 -sTCP:LISTEN
   # Si es un servicio esencial, limitarlo a loopback
   # Si no es esencial, detenerlo
   ```

2. **Verificar y activar firewall**:
   ```bash
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
   ```

### 🟡 IMPORTANTE (Hacer dentro de 24 horas)
3. **Ejecutar auditoría del software**:
   ```bash
   openclaw --help
   openclaw audit  # o security, doctor, etc.
   python3 -m hermes_cli.main --help
   ```

4. **Revisar logs manualmente**:
   ```bash
   find ~/Library/Logs -name "*.log" | grep -E "(claw|hermes)"
   tail -100 <log_file> | grep -E "(ERROR|WARN|FAIL|auth)"
   ```

5. **Inventariar credenciales**:
   ```bash
   cat ~/.config/openclaw/config.json
   cat ~/.config/hermes/config.json
   security find-generic-password -a "$USER" -s "openclaw"
   ```

### 🟢 RECOMENDADO (Hacer dentro de 48 horas)
6. **Rotar credenciales críticas** (ver `09_rotation_plan.md`)

7. **Limitar servicios no esenciales a loopback**:
   - Revisar configuración de cada servicio
   - Configurar `bind_address = 127.0.0.1`
   - Reiniciar servicios

## Qué NO Se Pudo Verificar

Debido a restricciones de permisos, NO se pudo verificar:

1. ❌ **Estado del firewall macOS** (requiere sudo)
2. ❌ **Identidad del proceso del puerto 5000** (requiere permisos elevados)
3. ❌ **Logs de acceso de los gateways** (archivos inaccesibles)
4. ❌ **Configuración de autenticación** (archivos inaccesibles)
5. ❌ **Secretos y credenciales** (archivos inaccesibles)
6. ❌ **Comandos de auditoría interna** (requiere aprobación)
7. ❌ **Historial de actividad** (logs inaccesibles)

## Conclusión

El sistema está **PARCIALMENTE SEGURO** porque:
- ✅ El gateway principal está correctamente aislado
- ⚠️ Hay otros puertos/services que requieren investigación
- ❌ No se puede confirmar si hubo intrusión previa
- ❌ No se puede verificar el estado del firewall

**No hay evidencia de exposición confirmada**, pero la falta de verificación en áreas críticas (logs, configuración, firewall) significa que **no se puede garantizar que no haya habido un incidente previo**.

## Próximos Pasos

1. **Usuario**: Verificar estado del firewall
2. **Usuario**: Identificar proceso del puerto 5000
3. **Usuario**: Ejecutar auditoría interna de OpenClaw/Hermes
4. **Usuario**: Revisar logs buscando actividad sospechosa
5. **Usuario**: Inventariar y rotar credenciales si es necesario

## Archivos de Auditoría

Todos los hallazgos detallados están en:
- `01_topologia.md` - Arquitectura de la instalación
- `02_red_y_puertos.txt` - Estado de puertos y red
- `03_firewall.txt` - Intento de verificación de firewall
- `04_docker.txt` - Verificación de Docker
- `05_proxy.txt` - Búsqueda de reverse proxy
- `06_security_audit.txt` - Intento de auditoría interna
- `07_logs_findings.md` - Intento de búsqueda de logs
- `08_secrets_inventory.md` - Inventario parcial de secretos
- `09_rotation_plan.md` - Plan de rotación de credenciales
- `10_vscode_check.md` - Verificación de extensiones VS Code
