# Analytics v2 - Clasificacion Proxy por Activo MVP

## Objetivo

Clasificar activos individuales en el universo de factores MVP usando reglas trazables,
sin forzar precision falsa.

## Orden de clasificacion

El clasificador aplica este orden:

1. mapping explicito por simbolo
2. fallback por `bloque_estrategico`
3. fallback por `sector`
4. `unknown` si no hay proxy razonable

## Base reutilizada del proyecto

La clasificacion se apoya en metadata ya existente:

- `ParametroActivo.bloque_estrategico`
- `ParametroActivo.sector`
- `ParametroActivo.tipo_patrimonial`

Y en mappings ya observables en:

- `cargar_metadata.py`
- `dashboard/selectors.py`

## Criterio MVP

- `Growth` y subsectores tecnologicos -> `growth`
- `Dividendos` -> `dividend`
- `Defensivo`, `Utilities`, `Salud`, `Consumo defensivo` -> `defensive`
- `Energia`, `Materiales`, `Mineria` -> `cyclical`
- bonos, cash y FCI -> `unknown` por defecto

## Trazabilidad

Cada clasificacion devuelve:

- `symbol`
- `factor`
- `source`
- `confidence`
- `notes`

## Limitaciones

- no clasifica todavia toda la cartera
- no agrega exposiciones
- no estima factores estadisticos
- mantiene `unknown` cuando no hay confianza razonable
