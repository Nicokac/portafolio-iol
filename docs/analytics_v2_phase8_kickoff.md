# Fase 8 - Apertura controlada

## Objetivo

Abrir Fase 8 sin saltar directo a desarrollos de alta complejidad o bajo respaldo de datos.

## Conclusion de arranque

El primer modulo avanzado recomendado no es:

- Monte Carlo
- factor model estadistico
- scenario engine parametrizable completo

El primer modulo avanzado recomendado es:

- `covariance-aware risk contribution`

## Razon

Es el modulo con mejor relacion entre:

- valor incremental sobre el MVP actual
- reutilizacion de codigo existente
- compatibilidad con la arquitectura actual
- riesgo metodologico controlable

## Reutilizacion ya disponible

- `apps/core/services/portfolio/covariance_service.py`
- `apps/core/services/portfolio/risk_parity_service.py`
- `apps/core/services/portfolio/optimizer_markowitz.py`
- `apps/core/services/analytics_v2/risk_contribution_service.py`
- tests cuantitativos ya existentes en `apps/core/tests/`

## Limites de esta apertura

Esta fase no habilita automaticamente:

- Monte Carlo
- betas robustas
- factor model estadistico
- optimizacion de frontera eficiente para producto

Esos temas siguen fuera de alcance hasta validar el primer modulo avanzado.

## Primer modulo propuesto para Fase 8

### `8.1 — Diseño de covariance-aware risk contribution`

Debe definir:

- objetivo exacto del modulo
- diferencias contra el MVP actual
- formula avanzada acotada
- requerimientos minimos de historia
- fallback cuando la covarianza no sea usable
- integracion con el resultado actual sin romperlo

## Riesgo detectado antes de implementarlo

`CovarianceService` hoy pivotea por `fecha_extraccion` completa y, igual que pasaba en el MVP de `risk contribution`, puede mezclar snapshots intradia como observaciones distintas.

Por lo tanto, antes de usarlo como base avanzada, el diseño de `8.1` debe decidir si:

1. normaliza a frecuencia diaria
2. exige una serie historica mas limpia
3. o ambas
