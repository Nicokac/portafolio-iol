# Analytics v2 - Scenario Signals MVP

## Objetivo

Derivar senales estructuradas reutilizables para alertas, planeacion y recomendaciones
a partir del modulo `scenario analysis`, sin acoplar todavia la logica al frontend ni al
`RecommendationEngine`.

## Input

- resultados de `ScenarioAnalysisService.analyze(...)`
- posiciones actuales normalizadas del portafolio

## Output

`ScenarioAnalysisService.build_recommendation_signals()` devuelve una lista serializable de
`RecommendationSignal`.

Senales MVP actuales:

- `scenario_vulnerability_tech`
- `scenario_vulnerability_argentina`
- `scenario_vulnerability_ars_devaluation`
- `scenario_liquidity_buffer`

## Regla MVP

- vulnerabilidad tech: se activa si `tech_shock` supera el umbral negativo definido
- vulnerabilidad Argentina: se activa si `argentina_stress` supera el umbral negativo definido
- vulnerabilidad ARS: se activa si `ars_devaluation` deja impacto neto negativo relevante
- amortiguacion por liquidez: se activa si la cartera tiene peso cash-like suficiente para
  actuar como buffer parcial frente a shocks

## Limitaciones

- usa shocks heurísticos, no calibración estadística
- no integra todavía con `RecommendationEngine`
- no publica señales compuestas ni ranking de prioridad final
- el buffer de liquidez se mide sobre posiciones actuales, no sobre cash de cuenta fuera de snapshots

## Extension futura

- integrar señales con motor de recomendaciones
- exponerlas por API/dashboard
- permitir thresholds configurables
