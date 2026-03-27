# Merge Prep - UX Simplicity v2

## Rama origen

- `feature/ux-simplicity-v2`

## Rama destino

- `develop`

## Estado general

- track principal de `ux_simplicity_v2_roadmap.md` implementado
- fase 3 de estabilizacion completada
- rama limpia y lista para integracion

## Alcance funcional cerrado

### Navegacion y arquitectura

- navbar principal reducido al flujo real del producto
- legacy encapsulado para `staff`
- `Resumen` consolidado como ruta canonica
- `DashboardContextMixin` desacoplado en contextos mas chicos por familia de vistas

### Planeacion

- flujo principal centrado en `Aportes`
- `Laboratorio` separado como superficie avanzada
- bloques secundarios plegados o diferidos
- segmentacion interna en:
  - `Validacion`
  - `Seguimiento`
  - `Comparadores`

### Estrategia y analitica

- `Estrategia` separada de `Cartera detallada`
- `Riesgo avanzado` como unica entrada profunda
- convergencia de `Analisis`, `Performance` y `Metricas` en `Centro analitico`
- templates absorbidos ya retirados

### Ops y superficies tecnicas

- `Ops` simplificada a version liviana
- syncs historicos IOL retirados del dashboard web
- residuos tecnicos del dashboard podados

### Endurecimiento de dominio

- `CheckConstraint` para parametros, montos y snapshots
- saneamiento del bug de exposiciones pais en snapshots
- endpoint `/api/portfolio/parameters/` estable aun sin configuracion persistida

## Documentacion alineada

- `docs/ux_simplicity_v2_roadmap.md`
- `docs/dashboard_surface_inventory.md`
- `docs/analytics_v2_feature_exposure_checklist.md`

## Validaciones ejecutadas durante el track

- `pytest apps/dashboard/tests/test_feature_flows.py -q --override-ini "addopts="`
- `pytest apps/dashboard/tests/test_views.py -q --override-ini "addopts="`
- `pytest apps/core/tests/test_portfolio_snapshot_service.py -q --override-ini "addopts="`
- `pytest apps/api/tests/test_views.py -q -k "portfolio_parameters_get or portfolio_parameters_update" --override-ini "addopts="`
- `python manage.py check`

## Riesgos residuales conocidos

- `Planeacion` sigue siendo la hoja mas densa del producto, aunque ya no compite de entrada con todo el contexto secundario
- `dashboard:performance` y `dashboard:metricas` siguen como redirects de compatibilidad
- el merge deberia vigilar conflictos en:
  - `apps/dashboard/views.py`
  - `templates/base.html`
  - `templates/dashboard/planeacion.html`
  - `templates/dashboard/estrategia.html`
  - `apps/dashboard/tests/test_views.py`

## Estrategia de merge sugerida

### Opcion recomendada

- merge normal a `develop` conservando historia del track

### Opcion alternativa

- squash merge si se quiere una historia mas corta orientada a producto

## Commits sugeridos para agrupar si se hace squash

1. `feat(ux): simplifica navegacion y separa superficies del flujo principal`
2. `feat(ux): enfoca planeacion y mueve herramientas avanzadas a laboratorio`
3. `feat(ux): separa estrategia ejecutiva, consolida analytics y crea centro analitico`
4. `feat(ux): compacta planeacion, segmenta bloques secundarios y aligera ops`
5. `feat(ux): endurece invariantes y poda residuos tecnicos del dashboard`
6. `fix(snapshot): normaliza distribucion por pais antes de persistir exposiciones`
7. `fix(api): devuelve parametros de portfolio por defecto cuando no hay configuracion activa`
8. `docs(ux): actualiza roadmap, inventario y cierre de merge`

## Checklist de integracion

1. actualizar `develop`
2. mergear `feature/ux-simplicity-v2`
3. correr:
   - `python manage.py migrate`
   - `python manage.py check`
   - `pytest apps/dashboard/tests/test_feature_flows.py -q --override-ini "addopts="`
   - `pytest apps/dashboard/tests/test_views.py -q --override-ini "addopts="`
   - `pytest apps/core/tests/test_portfolio_snapshot_service.py -q --override-ini "addopts="`
   - `pytest apps/api/tests/test_views.py -q -k "portfolio_parameters_get or portfolio_parameters_update" --override-ini "addopts="`
4. verificar manualmente:
   - `Resumen`
   - `Planeacion`
   - `Laboratorio`
   - `Estrategia`
   - `Centro analitico`
   - `Ops`
   - guardado de snapshot
5. revisar que `Laboratorio` no vuelva a mostrar warning por `portfolio/parameters`

## Cierre esperado tras merge

- el producto queda mas simple de navegar
- el flujo principal queda mas claro para decisiones de aporte, compra y rebalanceo
- las superficies tecnicas dejan de contaminar la UX principal
- el dashboard queda mas mantenible para una fase posterior de polish fino
