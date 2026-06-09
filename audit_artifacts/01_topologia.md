# Topología de la Instalación - Clawdbot/Clawdebot/OpenClaw

## Fecha de Auditoría
2025-06-09 06:36:11 -04

## Entorno Detectado
- **OS**: macOS (Darwin 25.5.0) arm64
- **Usuario**: felipe_gonzalez (uid=501, grupos: staff, admin, etc.)
- **Docker**: Instalado (v29.2.1)
- **Tipo de instalación**: Local (npm global)

## Servicios Detectados

### Gateway Principal: OpenClaw
- **Binario**: `/Users/felipe_gonzalez/.npm-global/lib/node_modules/openclaw/dist/index.js`
- **Comando**: `node .../openclaw/dist/index.js gateway --port 18789`
- **PID**: 53593
- **Usuario**: felipe_gonzalez
- **Tiempo de ejecución**: ~24 horas (iniciado Sun09AM)
- **Interfaz de escucha**:
  - `127.0.0.1:18789` (IPv4 loopback) ✓
  - `::1:18789` (IPv6 loopback) ✓
  - **NO escucha en 0.0.0.0** ✓

### Gateway Secundario: Hermes
- **Binario**: `/opt/homebrew/Cellar/python@3.11/3.11.15/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python`
- **Comando**: `python -m hermes_cli.main gateway run --replace`
- **PID**: 3057
- **Tiempo de ejecución**: Desde 23May26 (corriendo desde hace ~17 días)
- **Estado**: Requiere investigación adicional

## Tipo de Instalación
- **Método**: npm global (`~/.npm-global/lib/node_modules/openclaw`)
- **No Docker**: Los procesos corren nativamente, no en contenedores
- **No systemd service**: Corre como proceso de usuario, no como servicio del sistema

## Estado de Exposición (PRELIMINAR)
- **Gateway OpenClaw**: ESCUCHANDO SOLO EN LOOPBACK (127.0.0.1 y ::1)
  - **Riesgo de exposición externa**: BAJO (solo accesible localmente)
  - **Riesgo de acceso local**: MEDIO (si hay otros usuarios o malware)
- **Gateway Hermes**: REQUIERE INVESTIGACIÓN (puerto desconocido)

## Próximos Pasos
1. Verificar estado del firewall macOS
2. Identificar puerto de escucha del gateway Hermes
3. Revisar logs de ambos gateways
4. Verificar configuración de proxy/reverse proxy
