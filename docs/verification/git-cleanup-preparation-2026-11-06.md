# Informe de verificación del formato

## Alcance y resultados

La base de comparación es el commit público `06fbbdf08996043ce211ffd2fe137fd77a2a1a90`. Se revisaron 10 archivos Python; los cambios verificados fueron solo de formato. La comprobación inicial del alcance detectó nueve fallos de formato. La revisión global encontró un décimo, que también se corrigió.

En la revalidación final, Ruff informó que 280 archivos ya estaban formateados y que la comprobación global no encontró problemas. La comparación de AST sin atributos fue idéntica en los 10 archivos. La ejecución registrada incluyó 29 pruebas focalizadas aprobadas.

## Comandos reproducibles

Ejecutar desde la raíz del checkout, con un entorno de desarrollo ya activado y sus dependencias instaladas. `ruff` y `python` se resuelven desde ese entorno y son equivalentes a los ejecutables usados para registrar la revalidación; no se afirma que se invocaran mediante estos nombres o rutas exactos.

```sh
ruff format --check --no-cache .
ruff check --no-cache .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" PAPER_LLM_CLI=off PAPER_SEARCH_PROVIDER=fixture MCP_TRIFECTA_MODE=off RUN_LOCAL_ZOTERO_TESTS=0 python -m pytest -p no:cacheprovider tests/harness/test_command_spec.py tests/harness/test_orchestrator_log.py -o addopts='' --tb=short -q
```

## Límites

No se ejecutaron `make verify`, mypy, pruebas E2E ni CI nueva. Estos resultados no constituyen una garantía sobre comportamiento científico ni servicios live. La nueva versión de este informe no afirma que el snapshot actual esté aprobado.
