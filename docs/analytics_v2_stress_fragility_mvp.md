# Analytics v2 - Stress Fragility MVP

## Objetivo

Calcular la fragilidad del portafolio ante stresses extremos discretos reutilizando
escenarios ya definidos en `scenario analysis`.

## Input

- `StressCatalogService`
- `ScenarioAnalysisService`

## Output

`StressFragilityService.calculate(stress_key)` devuelve:

- `fragility_score`
- `total_loss_pct`
- `total_loss_money`
- `vulnerable_assets`
- `vulnerable_sectors`
- `vulnerable_countries`
- `metadata`

## Algoritmo MVP

1. resolver el stress en el catálogo
2. ejecutar todos los `scenario_keys` asociados
3. combinar impactos monetarios por activo, sector y país
4. calcular pérdida total
5. calcular `fragility_score` simple con:
   - severidad de pérdida
   - concentración de pérdida en top 3 activos
   - ajuste por liquidez cash-like

## Limitaciones

- el score no es probabilístico
- la combinación de shocks es heurística y aditiva
- depende de los escenarios cerrados ya definidos
- no integra todavía señales ni UI
