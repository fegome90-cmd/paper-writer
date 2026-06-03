# Paper Writer - Trifecta Documentation

> **Trifecta F1 Engine**: Repositorio blindado bajo la **Constitucion de Codigo Agentico v1.1**.

## [FILE] Estructura Neutral (Ley VII)

```
paper-writer/
|-- AGENTS.md                    # Constitucion y Gobernanza (Vinculante)
|-- skill.md                     # Reglas y contratos (Protocolo Fail-Closed)
|-- .ai/                         # [Neutral] Infraestructura agentica
|   |-- commands/                # Comandos personalizados
|   |-- hooks/                   # Automatizacion event-driven
|   |-- plans/                   # Planes de ejecucion
|   |__ traces/                  # Evidencia y logs de sesion
|-- scripts/
|   |__ trifecta_manager.sh      # Authoritative Daemon & Health Manager
|-- configs/
|   |-- anchors.yaml             # Semantic anchors for agents
|   |__ aliases.yaml             # Common phrase mappings
|-- Makefile                     # Unified Command Interface (F1 Style)
|-- biome.json                   # Quality: Formatter & Linter config
|-- pyrefly.toml                 # Quality: Type-checking config
|-- llms.txt                     # LLM Reference guide
|__ _ctx/                        # Context resources (PCC)
```

## [CLEAN] Repository Hygiene (Mandatory)

Para mantener el motor de Trifecta calibrado, el repositorio MUST estar limpio.

```bash
# Purga de worktrees redundantes
make clean
```

## [GO] Flujo de Onboarding

1. **Leer `AGENTS.md`** - Entender las 13 Leyes.
2. **Leer `skill.md`** - Activar el protocolo de validacion.
3. **Deep Context Activation** - Run `make warmup`.
4. **Leer `_ctx/prime_paper-writer.md`** - Cargar lista de lectura.

> [!IMPORTANT]
> **Toda mutacion sin plan previo es una violacion de la Ley I.**
