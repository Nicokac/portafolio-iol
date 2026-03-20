# Persistencia minima de historicos IOL

## Objetivo

Guardar precios diarios por simbolo desde IOL para reutilizarlos despues en analytics sin depender de requests en tiempo real durante render.

## Componentes

- modelo: `IOLHistoricalPriceSnapshot`
- servicio: `IOLHistoricalPriceService`

## Modelo

Campos persistidos:

- `simbolo`
- `mercado`
- `source`
- `fecha`
- `open`
- `high`
- `low`
- `close`
- `volume`

Clave unica:

- `simbolo + mercado + source + fecha`

## Servicio

### `sync_symbol_history(mercado, simbolo, params=None)`

- llama a `IOLAPIClient.get_titulo_historicos(...)`
- normaliza filas
- hace `update_or_create`

### `sync_current_portfolio_symbols(params=None)`

- toma simbolos actuales desde `ActivoPortafolioSnapshot`
- sincroniza una vez por `simbolo + mercado`

### `build_close_series(simbolo, mercado, dates)`

- devuelve serie diaria de cierres
- reutilizable por servicios de riesgo y metricas

## Integracion actual

Uso habilitado hoy:

- `RiskContributionService`
  - primera fuente de volatilidad por activo
- `VolatilityService`
  - fallback proxy de volatilidad de portafolio cuando no hay historia suficiente de `PortfolioSnapshot`
  - usa pesos actuales mas cierres IOL por simbolo

## Limitaciones

- no interpreta todavia splits ni ajustes
- no agrega UI de series historicas
- el fallback de `VolatilityService` es un proxy de composicion actual, no reemplaza la semantica principal basada en snapshots y TWR
- no hay todavia sync intradiario ni task de backfill historico extendido
