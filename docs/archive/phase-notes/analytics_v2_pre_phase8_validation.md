# Validacion minima antes de Fase 8

## Objetivo

Confirmar que los modulos MVP de Analytics v2 no tengan errores conceptuales evidentes antes de iniciar desarrollos mas complejos.

## Alcance revisado

1. `risk contribution`
2. `factor exposure proxy`
3. `stress fragility`
4. bloqueos por historico insuficiente

## Hallazgos

### Risk contribution

- se corrigio el uso de snapshots intradia como si fueran observaciones historicas independientes
- ahora la volatilidad historica por activo usa una observacion diaria por fecha
- caucion y cash management siguen excluidos del universo de riesgo

### Factor mapping

- los `unknown_assets` actuales corresponden principalmente a:
  - caucion
  - FCI de liquidez
  - bonos soberanos
  - CER
  - corporativos AR
- eso es consistente con el alcance actual del modelo factorial MVP

### Stress fragility

- se corrigio la base de `top3_loss_share`
- ahora la concentracion de perdida usa perdidas negativas brutas y no perdida neta total
- esto evita saturaciones artificiales del `fragility_score`

### Historico insuficiente

- volatilidad y metricas robustas siguen bloqueadas cuando no hay historia suficiente
- el sistema actual muestra `insufficient_history` con 3 snapshots / 90 dias

## Resultado

Con estos ajustes, la base MVP queda conceptualmente mas sana para evaluar una futura apertura de Fase 8.
