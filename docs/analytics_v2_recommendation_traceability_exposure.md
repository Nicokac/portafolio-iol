## Objetivo

Exponer en producto la trazabilidad mínima del modelo de riesgo usado por recomendaciones derivadas de `risk contribution`.

## Decisión aplicada

Se expone `modelo_riesgo` en:

- payload JSON de recomendaciones
- detalle secundario de `Planeación`

No se cambia:

- el título de la recomendación
- la prioridad
- la deduplicación
- la jerarquía visual principal

## Razón de UX

Mostrar siempre el modelo analítico como badge principal agregaría ruido.

En esta fase conviene:

- mantener foco en la acción recomendada
- mostrar la metodología solo como detalle secundario cuando existe

## Formato expuesto

En `Planeación`, una recomendación puede mostrar:

- `Activos: AAPL, MSFT`
- `Modelo de riesgo: covariance_aware`

o, si aplica fallback:

- `Modelo de riesgo: mvp_proxy`

## Alcance deliberadamente acotado

No se expone todavía en:

- `Resumen`
- `Estrategia`
- APIs analíticas dedicadas
- badges visuales específicos por modelo

## Extensión futura sugerida

Si la activación de covarianza se vuelve frecuente:

- convertir `modelo_riesgo` en badge visual
- agregar tooltip metodológico corto en `Planeación`
