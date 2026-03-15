# Analytics v2 - Expected Return Signals MVP

## Objetivo

Derivar señales reutilizables para planeación a partir del módulo de retorno esperado simple.

La integración MVP no modifica todavía `RecommendationEngine`.
Expone señales estructuradas para consumo posterior por planeación y recomendaciones.

## Señales implementadas

### 1. `expected_return_real_weak`

Se activa cuando el retorno real esperado simple queda en zona baja o negativa frente a inflación.

Uso:

- alertar que la composición actual no compensa suficientemente el contexto inflacionario

### 2. `expected_return_nominal_weak`

Se activa cuando no hay base para una señal real, pero la referencia nominal total queda moderada.

Uso:

- advertir que la estructura actual proyecta una referencia de retorno baja incluso nominalmente

### 3. `expected_return_liquidity_drag`

Se activa cuando:

- la liquidez/cash management pesa demasiado
- y su referencia esperada queda materialmente por debajo del bucket de equity

Uso:

- señalar posible costo de oportunidad por exceso de liquidez

## Limitaciones

- las señales dependen de la baseline del módulo, no de forecasting por activo
- el benchmark objetivo todavía es estructural, no configurable por usuario
- la planeación legacy aún no consume estas señales de forma directa
