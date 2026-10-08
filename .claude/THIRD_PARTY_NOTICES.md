# Avisos de terceros

Los skills y agentes de esta carpeta provienen de proyectos de código abierto. Sus licencias
aplican solo a estos archivos, no al resto del repositorio, que es propietario (ver `LICENSE` en la
raíz). Los textos completos están en `.claude/licenses/`.

No se instaló ningún hook de estos proyectos. `.claude/launch.json` es propio del repo.

## ECC — affaan-m/ECC

- **Origen:** https://github.com/affaan-m/ECC (commit `ef648e0`)
- **Licencia:** MIT, Copyright (c) 2026 Affaan Mustafa — `licenses/ECC-LICENSE`
- **Archivos, sin modificar:**
  - `skills/fastapi-patterns/`, `skills/python-patterns/`, `skills/python-testing/`,
    `skills/security-review/`, `skills/postgres-patterns/`, `skills/mle-workflow/`,
    `skills/react-patterns/`, `skills/react-testing/`
  - `agents/python-reviewer.md`, `agents/security-reviewer.md`, `agents/database-reviewer.md`,
    `agents/mle-reviewer.md`, `agents/react-reviewer.md`

## Impeccable — pbakaus/impeccable

- **Origen:** https://github.com/pbakaus/impeccable (commit `ffeda44`, skill 4.5.0)
- **Licencia:** Apache 2.0 — `licenses/impeccable-LICENSE`, con avisos en
  `licenses/impeccable-NOTICE.md`
- **Archivos, sin modificar:** `skills/impeccable/` y `agents/impeccable-*.md`
- **No incluido:** `hooks/hooks.json` del plugin original.
- **A tener en cuenta:** el lanzador `skills/impeccable/scripts/impeccable` descarga, la primera
  vez que se ejecuta, un binario desde las releases de GitHub del proyecto y lo guarda en
  `~/.impeccable/` (fuera del repo). Lo compara con un `.sha256` descargado del mismo lugar: eso
  detecta una descarga corrupta, no una release comprometida. Si el lanzador no se ejecuta, el
  skill funciona en modo de solo guía.

## The Agency — msitarzewski/agency-agents

- **Origen:** https://github.com/msitarzewski/agency-agents (commit `f99f6aa`)
- **Licencia:** MIT, Copyright (c) 2025 AgentLand Contributors — `licenses/agency-agents-LICENSE`
- **Archivos:**
  - `agents/privacy-engineer.md`, tomado de `engineering/engineering-privacy-engineer.md`
  - `agents/data-visualization-engineer.md`, tomado de
    `engineering/engineering-data-visualization-engineer.md`
- **Modificación:** en ambos, el campo `name` del encabezado se normalizó a minúsculas con guiones
  (`privacy-engineer`, `data-visualization-engineer`).
