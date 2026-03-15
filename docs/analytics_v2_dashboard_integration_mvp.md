# Analytics v2 - Dashboard Integration MVP

## Objetivo

Integrar Analytics v2 al producto sin mover lógica de cálculo a templates y sin romper la lectura actual del dashboard.

## Decisión de integración

La primera integración se hace en `Estrategia`.

Razonamiento:

- ya es la página con mayor densidad analítica
- permite exponer valor de v2 sin repartir cambios por toda la UI
- mantiene bajo el alcance del primer módulo de integración

## Patrón aplicado

1. los servicios v2 siguen calculando en `apps/core/services/analytics_v2/`
2. el dashboard consume un selector adaptador:
   - `get_analytics_v2_dashboard_summary()`
3. la vista solo inyecta ese resumen en contexto
4. el template renderiza tarjetas y tablas ya preparadas

## Qué se muestra

- `risk contribution`
- `scenario analysis`
- `factor exposure`
- `stress testing`
- `expected return simple`
- señales agregadas de Analytics v2

## Limitaciones

- integración solo en `Estrategia`
- no hay gráficos específicos de v2 todavía
- no hay endpoint API nuevo en esta fase
- no hay integración con recomendaciones legacy en esta fase
