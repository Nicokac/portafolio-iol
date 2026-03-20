# Persistencia mínima de históricos IOL

## Objetivo

Guardar precios diarios por símbolo desde IOL para reutilizarlos después en analytics sin depender de requests en tiempo real durante render.

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

Clave única:

- `simbolo + mercado + source + fecha`

## Servicio

### `sync_symbol_history(mercado, simbolo, params=None)`

- llama a `IOLAPIClient.get_titulo_historicos(...)`
- normaliza filas
- hace `update_or_create`

### `sync_current_portfolio_symbols(params=None)`

- toma símbolos actuales desde `ActivoPortafolioSnapshot`
- sincroniza una vez por `simbolo + mercado`

### `build_close_series(simbolo, mercado, dates)`

- devuelve serie diaria de cierres
- pensada para el siguiente módulo de integración con analytics

## Limitaciones

- no interpreta todavía splits ni ajustes
- no agrega UI
- no se conecta todavía a `RiskContributionService`
- no hace scheduling automático
