# Plan de Rotación de Credenciales

## Fecha de Auditoría
2025-06-09 06:36:11 -04

## Contexto
Este plan se basa en la arquitectura típica de Clawdebot/Clawdbot/Moltbot. La rotación real depende de las credenciales específicas configuradas, que no pudieron ser inventariadas debido a restricciones de permisos.

## Plan de Rotación Prioritario

### FASE 1 - Rotación Inmediata (Si hubo exposición)

#### 1. Token del Gateway
- **Qué**: Token de autenticación del gateway (si existe)
- **Por qué**: Si el puerto 5000 estuvo expuesto, este token podría haber sido comprometido
- **Cómo**:
  - Generar nuevo token con `openclaw token new` o comando equivalente
  - Actualizar configuración en `~/.config/openclaw/config.json`
  - Reiniciar el servicio
- **Verificación**: Confirmar que el servicio funciona con el nuevo token

#### 2. API Keys de LLM Providers
- **Qué**: OpenAI API Key, Anthropic API Key (si están configuradas)
- **Por qué**: Estas keys suelen tener permisos amplios y son valiosas
- **Cómo**:
  - Ir al dashboard del proveedor (OpenAI/Anthropic)
  - Revocar la key antigua
  - Crear nueva key con permisos mínimos necesarios
  - Actualizar configuración local
- **Verificación**: Hacer un test request para confirmar funcionalidad

### FASE 2 - Rotación Pronta (Dentro de 24-48 horas)

#### 3. Tokens de Integraciones
- **Qué**: Tokens de Slack, Discord, GitHub, etc.
- **Por qué**: Aunque tienen permisos más limitados, podrían ser usados para spam o acceso a repositorios
- **Cómo**:
  - **Slack**: Ir a Slack App settings -> OAuth Tokens -> Revoke
  - **Discord**: Discord Developer Portal -> Bot -> Reset Token
  - **GitHub**: Settings -> Developer settings -> Personal access tokens -> Revoke
- **Verificación**: Desconectar y reconectar las integraciones

#### 4. Credenciales de Servicios Académicos
- **Qué**: Zotero API Key, Semantic Scholar, Crossref, arXiv
- **Por qué**: Pueden tener acceso a datos del usuario o permitir scraping
- **Cómo**:
  - Ir al dashboard de cada servicio
  - Revocar la key antigua
  - Generar nueva key con scopes mínimos
  - Actualizar configuración local
- **Verificación**: Hacer una búsqueda o query de prueba

### FASE 3 - Rotación Programada (Dentro de 1 semana)

#### 5. Credenciales de Base de Datos
- **Qué**: Si hay bases de datos SQLite o PostgreSQL
- **Por qué**: Menos crítico pero buena práctica
- **Cómo**:
  - Cambiar contraseña del usuario de base de datos
  - O crear nuevo usuario con permisos necesarios
  - Actualizar connection strings
- **Verificación**: Conectar a la DB con nuevas credenciales

#### 6. Keychain Entries
- **Qué**: Entradas en keychain relacionadas con "claw", "hermes", "claude"
- **Por qué**: Pueden contener tokens o keys cached
- **Cómo**:
  - Revisar con `security find-generic-password -a "$USER" -s "servicio"`
  - Borrar entradas sospechosas o desactualizadas
  - Las apps volverán a pedir credenciales si son necesarias
- **Verificación**: Ejecutar comandos que requieran autenticación

## Comandos Útiles para Rotación

### OpenClaw (probables comandos)
```bash
# Generar nuevo token
openclaw auth token-new
openclaw token rotate
openclaw config set-token

# Actualizar API keys
openclaw config set openai.api_key <new-key>
openclaw config set anthropic.api_key <new-key>

# Verificar configuración
openclaw config list
```

### Hermes CLI (probables comandos)
```bash
# Rotar credenciales
python3 -m hermes_cli.main auth rotate
python3 -m hermes_cli.main config set-token

# Actualizar integraciones
python3 -m hermes_cli.main integrations refresh
```

### Keychain macOS
```bash
# Listar entradas relacionadas
security find-generic-password -a "$USER" -s "openclaw" -g
security find-generic-password -a "$USER" -s "hermes" -g
security find-generic-password -a "$USER" -s "claude" -g

# Borrar entrada (requiere confirmación)
security delete-generic-password -a "$USER" -s "openclaw"
```

## Precauciones Durante Rotación

### Antes de Rotar
1. **Backup de configuración**: Guardar copia de archivos config
2. **Documentar keys actuales**: Anotar prefijos/sufijos para poder identificarlas después
3. **Verificar dependencias**: Confirmar qué servicios usan cada credencial
4. **Preparar rollback**: Tener plan por si algo falla

### Durante Rotación
1. **Rotar una credencial a la vez**: Para identificar problemas fácilmente
2. **Verificar inmediatamente**: Probar que el servicio funciona después de cada cambio
3. **Monitorear logs**: Revisar que no hay errores de autenticación
4. **Documentar cambios**: Mantener registro de qué se cambió y cuándo

### Después de Rotar
1. **Confirmar cleanup**: Verificar que las credenciales viejas fueron revocadas
2. **Revisar permisos**: Confirmar que las nuevas credenciales tienen permisos mínimos
3. **Actualizar documentación**: Documentar las nuevas credenciales (sin valores reales)
4. **Monitorear actividad**: Revisar logs en los días siguientes para detectar anomalías

## Evaluación de Prioridad

### CRÍTICA (Si hubo exposición)
- Token del gateway
- API Keys de LLM providers

### ALTA (Dentro de 24-48 horas)
- Tokens de integraciones (Slack, Discord, GitHub)
- API keys de servicios académicos

### MEDIA (Dentro de 1 semana)
- Credenciales de base de datos
- Keychain entries

### BAJA (Rotación periódica)
- Tokens con permisos muy limitados
- API keys de servicios no críticos

## Limitaciones
Este plan es genérico porque no se pudo acceder a los archivos de configuración reales. La rotación específica depende de las credenciales configuradas, que el usuario debe identificar manualmente.
