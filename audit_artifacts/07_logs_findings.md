# Logs - NO ACCESIBLES

## Fecha de Auditoría
2025-06-09 06:36:11 -04

## Intentos de Acceso a Logs
No se pudo acceder a los logs de los servicios debido a restricciones de permisos del sistema.

## Ubicaciones Probables de Logs

### OpenClaw
- Ubicación desconocida (posiblemente en ~/.config/openclaw/ o ~/Library/Logs/)
- Tipo de logs: Access logs, error logs, tool execution logs

### Hermes
- Ubicación desconocida (posiblemente en ~/.config/hermes/ o ~/Library/Logs/)
- Tipo de logs: Gateway logs, request logs, authentication logs

## Comandos Requeridos
```bash
# Buscar archivos de log
find ~/Library/Logs -name "*.log" | grep -E "(claw|hermes|molt)"
find ~/.config -name "*.log" | grep -E "(claw|hermes|molt)"
find ~ -name "*.log" -path "*/.claw*" -o -name "*.log" -path "*/.hermes*"

# Verificar logs del sistema
log show --predicate 'process == "openclaw"' --last 1d
log show --predicate 'process == "hermes"' --last 1d

# Si usan journal (Linux)
journalctl -u openclaw --since "24 hours ago"
journalctl -u hermes --since "24 hours ago"
```

## Información Crítica que Podrían Contener
- **IPs de acceso**: Origen de las conexiones al gateway
- **Timestamps**: Momento de cada request
- **Endpoints solicitados**: Qué tools/funciones se invocaron
- **Resultados de autenticación**: Intentos fallidos exitosos
- **Exportaciones de datos**: Si hubo exportación de configuración o datos
- **Actividad anómala**: Patrones sospechosos de uso

## Evaluación de Riesgo
- **LOGS NO ACCESIBLES**: No se pudo verificar actividad histórica
- **SEÑALES DE INTRUSIÓN**: NO SE PUDO DETERMINAR
- **RIESGO RESIDUAL**: DESCONOCIDO
- **PRIORIDAD**: ALTA - Acceder a logs para verificar si hubo uso no autorizado

## Recomendación Inmediata
El usuario debe revisar manualmente los logs para buscar:
1. IPs desconocidas accediendo a los gateways
2. Actividad en horas inusuales
3. Exportaciones de configuración
4. Ejecución de tools sensibles (shell, file system)
5. Múltiples fallos de autenticación

## Limitaciones
No se pudo acceder a ningún log debido a restricciones de permisos del sistema.
