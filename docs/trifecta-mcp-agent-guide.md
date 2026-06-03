# Guía de Herramientas MCP de Trifecta para Agentes

Esta guía define **exactamente cuándo y cómo** los agentes de IA deben usar cada una de las 15 herramientas expuestas por el servidor MCP de Trifecta. 

**Anti-Patrón (The "One-Tool MCP"):** No uses `ctx_oracle` para todo. Si necesitas el path más corto, usa `ctx_graph`. Si necesitas la firma de la función, usa `ast_hover`. 

---

## 1. Búsqueda Semántica y Recuperación de Código

### `ctx_search`
- **When to use ctx_search**: Cuando necesitas buscar un concepto por su descripción natural, un término genérico, o cuando no conoces el nombre exacto de la función/clase.
- **Ejemplo**: "Cómo funciona el sistema de gates", "dónde se guarda el estado".

### `ctx_get`
- **When to use ctx_get**: Cuando ya tienes el `id` de un chunk (obtenido vía `ctx_search` o `ctx_oracle`) y necesitas leer el archivo o el fragmento completo sin truncar.

---

## 2. Oráculo (Fusión de Señales)

### `ctx_oracle`
- **When to use ctx_oracle**: Cuando inicias una investigación arquitectónica amplia. El oráculo fusiona AST, PRIME y Graph. Usa esto para consultas iniciales como "impact of changing ManuscriptState" o "where is Orchestrator defined". Si la fidelidad devuelta es `degraded` o `fallback`, cambia inmediatamente a herramientas específicas de grafo.

---

## 3. Navegación Estructural Pura (El Grafo)

Las herramientas de `ctx_graph` son deterministas y O(1) o O(E). Son **superiores al oráculo** cuando conoces el símbolo objetivo.

### `ctx_graph` (action="callers")
- **When to use callers**: Para trazar quién llama a tu función. Crucial antes de modificar o eliminar un método para evaluar quién se romperá.

### `ctx_graph` (action="callees")
- **When to use callees**: Para saber qué funciones internas ejecuta un método. Útil para entender dependencias ocultas.

### `ctx_graph` (action="importers")
- **When to use importers**: Para ver qué archivos (módulos) importan el archivo actual.

### `ctx_graph` (action="import_targets")
- **When to use import_targets**: Para listar qué archivos importa tu módulo.

### `ctx_graph` (action="subclasses")
- **When to use subclasses**: Cuando alteras una clase base (ej. `ToolWrapper`) y necesitas actualizar TODAS las implementaciones. 

### `ctx_graph` (action="parents")
- **When to use parents**: Para ver de quién hereda una clase y entender qué métodos tiene disponibles.

### `ctx_graph` (action="path")
- **When to use path**: Para encontrar si existe una ruta de llamadas entre dos funciones (ej. de `Orchestrator` a `ManuscriptState`). Determina límites de capas arquitectónicas.

### `ctx_graph` (action="impact")
- **When to use impact**: Blast radius. Retorna los llamadores transitivos de un símbolo hasta N niveles.

### `ctx_graph` (action="orphans")
- **When to use orphans**: Para detectar código sin llamadas estáticas. Fundamental en auditorías de limpieza.

### `ctx_graph` (action="cycles")
- **When to use cycles**: Para detectar dependencias circulares antes de enviar un Pull Request.

### `ctx_graph` (action="hubs")
- **When to use hubs**: Para entender la "columna vertebral" del sistema. Muestra los nodos más conectados.

### `ctx_graph` (action="overview")
- **When to use overview**: Para obtener un chequeo de salud en 1 segundo (hubs, orphans, ciclos) al entrar a un nuevo repositorio.

### `ctx_graph` (action="status" / "search")
- **When to use status**: Para validar si el grafo existe.
- **When to use search**: Búsqueda difusa súper rápida solo por nombre de símbolo, sin semántica.

---

## 4. AST y Tipado Estático

### `ast_analyze`
- **When to use ast_analyze**: Para extraer todos los símbolos (clases, métodos, funciones) de un archivo en ~10ms sin tener que leerlo. Ideal para mapeo de APIs.

### `ast_hover`
- **When to use ast_hover**: Para simular un "mouse hover" de IDE. Retorna los tipos, docstrings y firma de una variable/función. Requiere Pyright activo.

---

## 5. Mantenimiento y Diagnóstico

### `ctx_health`
- **When to use ctx_health**: Diagnóstico general rápido de salud del repositorio.

### `ctx_oracle_health`
- **When to use ctx_oracle_health**: Cuando creas que la información devuelta por el oráculo es dudosa. Retorna issues con auto-fix hints.

### `ctx_validate`
- **When to use ctx_validate**: Para chequear que el Context Pack en `_ctx/` no está corrupto, y ver cuántos archivos están desactualizados.

### `ctx_reindex_graph`
- **When to use ctx_reindex_graph**: **CRÍTICO**. Úsalo inmediatamente después de modificar, renombrar o eliminar archivos `.py` para que el grafo refleje la realidad.

### `ctx_reset`
- **When to use ctx_reset**: Acción destructiva extrema. Solo si el índice está irremediablemente roto.

### `ctx_plan`
- **When to use ctx_plan**: Genera un plan de acción estricto a partir del índice PRIME sin RAG.

### `ctx_calibrate`
- **When to use ctx_calibrate**: Para auto-calibrar los pesos TF-IDF en base a un dataset de pruebas. Rara vez usado por agentes operativos.
