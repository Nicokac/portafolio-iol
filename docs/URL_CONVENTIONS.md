# URL Conventions

## Goal
Avoid route shadowing between dashboard pages and data-list applications.

## Rules
1. Dashboard UI pages use root-level or `panel/` prefixes.
2. Data-list applications keep their own top-level prefixes:
   - `/resumen/` -> `resumen_iol`
   - `/portafolio/` -> `portafolio_iol`
   - `/operaciones/` -> `operaciones_iol`
   - `/parametros/` -> `parametros`
3. API endpoints stay under `/api/`.
4. Health endpoint stays at `/health/`.
5. New include patterns in `config/urls.py` must be reviewed for collisions before merge.

## Current critical paths
- `/` -> `dashboard:dashboard`
- `/panel/resumen/` -> `dashboard:resumen`
- `/analisis/` -> `dashboard:analisis`
- `/estrategia/` -> `dashboard:estrategia`
- `/resumen/` -> `resumen_iol:resumen_list`
