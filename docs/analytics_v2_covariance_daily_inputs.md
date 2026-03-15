# Preparacion de inputs diarios para covarianza

## Objetivo

Evitar que `CovarianceService` use snapshots intradia como si fueran observaciones historicas independientes.

## Cambio aplicado

La serie de precios para covarianza ahora:

1. normaliza `fecha_extraccion` a fecha diaria
2. conserva la ultima observacion valida del dia por activo
3. pivotea sobre esa frecuencia diaria
4. calcula retornos diarios solo sobre esa serie normalizada

## Impacto

- mejora consistencia metodologica para Fase 8
- reduce falsa sensacion de historia suficiente
- alinea el servicio cuantitativo con la correccion ya aplicada en `risk contribution` MVP

## Limitaciones

- sigue usando snapshots internos del sistema, no precios externos ajustados
- no resuelve aun series muy cortas o iliquidas
- no introduce estimadores robustos de covarianza
