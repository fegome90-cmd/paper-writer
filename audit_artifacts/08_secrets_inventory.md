# Inventario de Secretos - PARCIAL

## Fecha de Auditoría
2025-06-09 06:36:11 -04

## Limitaciones
No se pudo acceder a archivos de configuración y credenciales debido a restricciones de permisos del sistema.

## Ubicaciones Probables de Secretos

### OpenClaw
- **Configuración**: `~/.config/openclaw/config.json`
- **Credenciales**: Posiblemente en `~/.config/openclaw/credentials.json`
- **Tokens**: Podrían estar en `~/.openclaw/` o keychain del sistema

### Hermes
- **Configuración**: `~/.config/hermes/config.json` o `~/.hermes/`
- **Credenciales**: Posiblemente integradas con otras credenciales del sistema

### Claude Code / Claude CLI
- **Credenciales**: Probablemente en Keychain de macOS
- **API Keys**: Anthropic API keys para Claude

### Integraciones Posibles
Basado en el contexto del proyecto, las integraciones podrían incluir:
- **OpenAI**: API keys para GPT models
- **Anthropic**: API keys para Claude
- **Slack**: Bot tokens para integraciones
- **Discord**: Bot tokens
- **GitHub**: Personal access tokens
- **Zotero**: API keys (si hay integración académica)
- **Semantic Scholar**: API keys
- **Crossref / arXiv**: API keys para búsquedas académicas

## Comandos Requeridos para Inventario Completo
```bash
# Revisar archivos de configuración (con redacción de secretos)
cat ~/.config/openclaw/config.json | jq 'with_entries(select(.value | type != "string"))'
cat ~/.config/hermes/config.json | jq 'with_entries(select(.value | type != "string"))'

# Buscar archivos con secretos
find ~ -name ".env*" -o -name "*credentials*" -o -name "*secrets*" | grep -v ".git"

# Revisar keychain (macOS)
security find-generic-password -a "$USER" -s "openclaw" 2>/dev/null
security find-generic-password -a "$USER" -s "hermes" 2>/dev/null
security find-generic-password -a "$USER" -s "claude" 2>/dev/null

# Buscar tokens en config files
grep -r "token\|key\|secret\|password" ~/.config/openclaw/ 2>/dev/null | grep -v "Binary"
grep -r "token\|key\|secret\|password" ~/.config/hermes/ 2>/dev/null | grep -v "Binary"
```

## Tipos de Secretos a Buscar (Redactados)
- **API Keys**: `sk-***` o `ak-***` (prefijo + sufijo)
- **Tokens Bearer**: `eyJ***` (JWT tokens, solo prefijo)
- **OAuth Tokens**: `oauth_token=***`, `access_token=***`
- **Bot Tokens**: `xoxb-***` (Slack), `MTAw***` (Discord)
- **GitHub Tokens**: `ghp_***`, `github_pat_***`
- **Database URLs**: `postgres://user:***@host`
- **Service Account Credentials**: Archivos JSON grandes (revisar estructura)

## Evaluación de Riesgo
- **INVENTARIO INCOMPLETO**: No se pudo acceder a la mayoría de los archivos
- **SECRETOS NO VERIFICADOS**: Desconocido si hay secretos expuestos
- **INTEGRACIONES NO DOCUMENTADAS**: No se sabe qué servicios están configurados
- **PRIORIDAD**: CRÍTICA - Acceder a archivos de configuración para inventariar secretos

## Recomendación Inmediata
El usuario debe revisar manualmente:

1. **Archivos de configuración principal**:
   - `~/.config/openclaw/config.json`
   - `~/.config/hermes/config.json`

2. **Keychain del sistema**:
   - Buscar entradas relacionadas con "claw", "hermes", "claude"
   - Verificar fecha de creación y último acceso

3. **Archivos .env o credentials**:
   - Buscar en directorios del proyecto
   - Revisar variables de entorno

## Plan de Rotación (Priorizado)
Una vez identificados los secretos, rotar en este orden:

### PRIORIDAD ALTA (Rotación Inmediata)
1. **Tokens de gateway**: Si el puerto 5000 estuvo expuesto
2. **API Keys con permisos amplios**: OpenAI, Anthropic
3. **OAuth tokens activos**: Slack, Discord, GitHub

### PRIORIDAD MEDIA (Rotación Pronta)
1. **Tokens de servicios específicos**: Zotero, Semantic Scholar
2. **Credenciales de base de datos** (si aplica)

### PRIORIDAD BAJA (Rotación Programada)
1. **Tokens de servicios no críticos**
2. **API keys con permisos limitados**

## Limitaciones
No se pudo inventariar ninguno de los secretos debido a restricciones de permisos del sistema.
