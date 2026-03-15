# Analytics v2 - Expected Return Simple MVP

## Objetivo

Dar una referencia estructural y explicable de retorno esperado a partir de la composicion actual del portafolio.

No busca pronosticar retornos por activo ni vender precision inexistente.

## Inputs

- posiciones actuales normalizadas
- benchmarks historicos disponibles
- referencia macro local de BADLAR
- referencia observada de inflacion

## Algoritmo MVP

1. agrupar posiciones actuales en tres buckets simples:
   - `equity_beta`
   - `fixed_income_ar`
   - `liquidity_ars`
2. asignar a cada bucket una referencia estructural:
   - equity -> `SPY` / `cedear_usa`
   - renta fija AR -> `EMB` / `bonos_ar`
   - liquidez -> `BADLAR`
3. si una referencia viva no tiene historia suficiente:
   - usar fallback estatico ya institucionalizado en `ParametrosBenchmark`
4. ponderar el retorno esperado de cada bucket por su peso actual en market value
5. si hay referencia de inflacion disponible:
   - calcular retorno esperado real simple

## Outputs

- `expected_return_pct`
- `real_expected_return_pct`
- `by_bucket`
- metadata metodologica con warnings y confidence

## Limitaciones

- es una baseline estructural, no un forecast preciso
- equity local y global comparten el proxy de equity del MVP
- la renta fija AR usa un proxy de benchmark, no curva propia por instrumento
- el retorno real depende de la referencia de inflacion disponible

## Extension futura

- integrar con planeacion
- separar equity local de equity global si el proyecto incorpora referencia robusta propia
- refinar buckets sin romper el contrato actual
