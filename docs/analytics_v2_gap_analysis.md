# Analytics v2 - Gap Analysis de Datos

## Objetivo

Determinar si los datos actuales del proyecto alcanzan para implementar cada modulo previsto de Analytics v2 en version MVP, identificar brechas reales y dejar documentados los proxys y fallbacks metodologicamente aceptables.

Este documento no redefine la metodologia financiera vigente. Complementa:

- `docs/portfolio_analytics_v2_spec.md`
- `docs/analytics_v2_architecture.md`
- `docs/analytics_v2_data_contracts.md`
- `docs/financial_methodology.md`

## Resumen ejecutivo

La conclusion general es esta:

- el proyecto ya tiene datos suficientes para un MVP util de `risk contribution`
- ya tiene base suficiente para un MVP heuristico de `scenario analysis`
- tiene metadata suficiente para un primer `factor exposure proxy`, aunque con confianza desigual segun activo
- ya existe una base reutilizable para `stress testing` heuristico ampliado
- tiene insumos suficientes para un `expected return simple` explicable y controlado
- no tiene todavia base adecuada para modelos avanzados de covarianza, betas robustas, multifactor estadistico o simulacion avanzada

## Inventario operativo de datos disponibles

### Posiciones actuales

Fuentes reutilizables:

- `ActivoPortafolioSnapshot`
- `ResumenCuentaSnapshot`
- `ParametroActivo`

Capacidad actual:

- valorizado por instrumento
- moneda operativa
- ganancia/perdida
- tipo de instrumento
- sector
- pais de exposicion
- bucket estrategico
- tipo patrimonial
- disponible inmediato

Utilidad para v2:

- base principal para `risk contribution`
- base principal para `scenario analysis`
- base principal para `factor exposure proxy`
- base principal para `stress testing`

### Series historicas del portafolio

Fuentes reutilizables:

- `PortfolioSnapshot`
- `PositionSnapshot`
- `OperacionIOL`
- `TWRService`
- `TemporalMetricsService`
- `VolatilityService`

Capacidad actual:

- patrimonio historico agregado
- posiciones historicas por fecha
- flujos via operaciones
- retornos netos de flujos
- drawdown y volatilidad con warnings por historia insuficiente

Utilidad para v2:

- volatilidad proxy cuando exista historia suficiente
- validacion temporal basica de riesgo
- soporte parcial para expected return y stress contextual

Limitacion importante:

- la calidad del historico depende de continuidad real de snapshots
- cuando la historia reciente es corta, la confianza de metricas temporales debe degradarse

### Benchmarks y macro local

Fuentes reutilizables:

- `BenchmarkSnapshot`
- `BenchmarkSeriesService`
- `MacroSeriesSnapshot`
- `LocalMacroSeriesService`

Capacidad actual:

- SPY como referencia CEDEAR USA
- EMB como proxy de bonos argentinos en USD
- BADLAR para liquidez ARS
- USDARS oficial mayorista BCRA
- IPC nacional

Utilidad para v2:

- baseline para expected return simple
- soporte para escenarios de liquidez, inflacion y FX
- referencia para sensibilidad y narrativas de riesgo macro

### Servicios analiticos ya existentes

Fuentes reutilizables:

- `AttributionService`
- `StressTestService`
- `TrackingErrorService`
- `RecommendationEngine`

Utilidad para v2:

- agrupacion por activo, sector, pais y bucket
- shocks heuristicos ya operativos
- benchmark compuesto ya institucionalizado
- motor de recomendaciones como consumidor futuro de senales v2

## Matriz de suficiencia por modulo

### 1. Risk Contribution

#### Estado de datos: suficiente para MVP

Datos disponibles y reutilizables:

- peso patrimonial por activo desde `ActivoPortafolioSnapshot`
- taxonomia por activo desde `ParametroActivo`
- volatilidad historica del portafolio agregada desde `VolatilityService`
- historia de posiciones y patrimonio desde snapshots
- agregacion por sector, pais y tipo ya reutilizable via selectores y attribution

Brechas reales:

- no hay volatilidad historica robusta por instrumento para toda la cartera
- no hay matriz de covarianza por activo lista para produccion
- no hay betas o factores estadisticos por instrumento

Decision metodologica MVP:

`risk contribution` puede implementarse con:

- `risk_score = peso * volatilidad_proxy`
- `contribution_pct = risk_score / suma_risk_score`

Orden aceptable de volatilidad proxy:

1. volatilidad historica por activo si existe y es suficiente
2. volatilidad derivada de snapshots/series del activo si existe
3. volatilidad proxy por tipo de activo o bucket
4. fallback explicito documentado

Proxys y fallbacks permitidos:

- CEDEAR/ETF equity: proxy de volatilidad equity internacional
- bonos AR: proxy de volatilidad renta fija AR / emergentes
- cash management y caucion: volatilidad baja o contribucion casi nula
- liquidez operativa: contribucion cero o muy cercana a cero

Riesgo principal del modulo:

- sobreinterpretar el score como contribucion marginal real de un modelo con covarianza

Conclusion:

- suficiente para MVP explicativo
- no suficiente para una version institucional covariance-aware

### 2. Scenario Analysis

#### Estado de datos: suficiente para MVP heuristico

Datos disponibles y reutilizables:

- clasificacion por activo, pais, sector, moneda y bucket desde `ParametroActivo`
- composicion actual desde `ActivoPortafolioSnapshot`
- shocks heuristicos ya existentes en `StressTestService`
- benchmark compuesto y macro local para contexto de escenarios

Brechas reales:

- no hay elasticidades empiricas por activo
- no hay estimacion de beta real por factor o benchmark para toda la cartera
- no hay motor de correlacion entre shocks

Decision metodologica MVP:

`scenario analysis` debe ser heuristico, auditable y cerrado.

Escenarios viables hoy:

- caida SPY -10% / -20%
- shock tech
- stress Argentina
- devaluacion ARS
- stress emergentes
- suba de tasas USA

Proxys y fallbacks permitidos:

- sensibilidad por tipo de activo
- sensibilidad por pais de exposicion
- sensibilidad por sector
- sensibilidad por moneda economica
- liquidez sin shock o con impacto nulo/sustancialmente menor

Riesgo principal del modulo:

- presentar impactos como forecasting preciso en lugar de sensibilidad heuristica

Conclusion:

- suficiente para MVP de escenarios cerrados y trazables
- insuficiente para motor parametrico o estadisticamente calibrado

### 3. Factor Exposure Proxy

#### Estado de datos: suficiente con confianza media

Datos disponibles y reutilizables:

- bucket estrategico
- sector
- tipo patrimonial
- pais
- mappings ya usados por recomendaciones y dashboards

Brechas reales:

- no existe hoy un mapa explicito de factores por simbolo
- no hay dataset fundamental o multifactor para todos los instrumentos
- algunos activos locales o FCI no tienen etiqueta factorial natural directa

Decision metodologica MVP:

`factor exposure proxy` debe partir de reglas controladas y trazables.

Orden aceptable de clasificacion:

1. mapping explicito por simbolo cuando el activo lo requiera
2. fallback por bucket estrategico
3. fallback por sector o tipo de activo
4. `unknown` si no hay confianza razonable

Factores iniciales viables:

- growth
- value
- quality
- dividend
- defensive
- cyclical

Proxys y fallbacks permitidos:

- CEDEAR big tech: growth
- utilities y salud defensiva: defensive
- telecom y consumo defensivo maduros: dividend/defensive
- FCI cash management y liquidez: fuera de clasificacion o `defensive/cash-like` segun contrato final
- bonos AR: no forzar factor equity; permitir bucket separado o `unknown`

Riesgo principal del modulo:

- falso sentido de precision factorial en activos sin clasificacion confiable

Conclusion:

- suficiente para MVP proxy y explicativo
- insuficiente para factor model robusto o data-driven

### 4. Stress Testing ampliado

#### Estado de datos: suficiente para MVP heuristico reutilizando base actual

Datos disponibles y reutilizables:

- `StressTestService` ya aplica shocks simples sobre el portafolio actual
- metadata por activo para shocks por pais, sector y tipo
- macro local y benchmark para contextualizar severidad

Brechas reales:

- no hay historia de eventos extremos suficientemente modelada
- no hay engine de correlacion ni cascadas de segundo orden
- no hay calibracion por drawdowns historicos instrumentales de toda la cartera

Decision metodologica MVP:

ampliar el stress testing actual, no reemplazarlo.

Proxys y fallbacks permitidos:

- shocks severos cerrados por pais/sector/moneda
- score de fragilidad a partir de perdida estimada + concentracion + liquidez
- ranking de vulnerabilidad por activo/sector/pais

Riesgo principal del modulo:

- confundir stress heuristico con perdida esperada probabilistica

Conclusion:

- suficiente para MVP ampliado y util para planeacion
- insuficiente para stress engine institucional o probabilistico

### 5. Expected Return Simple

#### Estado de datos: suficiente para MVP prudente y explicable

Datos disponibles y reutilizables:

- benchmark compuesto actual
- BADLAR
- IPC
- USDARS oficial mayorista
- clasificacion por activo y bucket
- TWR y retornos historicos del portafolio

Brechas reales:

- no hay expected return por instrumento calibrado
- no hay modelo de primas de riesgo por clase local completo
- no hay consenso fundamental integrado para equity y bonos

Decision metodologica MVP:

`expected return simple` debe ser una referencia estructural, no un forecast.

Baselines aceptables:

- benchmark asociado por bucket
- banda simple por asset class
- retorno real vs inflacion/BADLAR para liquidez y segmentos conservadores

Proxys y fallbacks permitidos:

- CEDEAR USA: baseline de benchmark asociado
- bonos AR: baseline emergente/bonos AR proxy
- liquidez ARS: BADLAR
- cash management: BADLAR o tasa monetaria similar

Riesgo principal del modulo:

- vender precision donde solo existe una referencia orientativa

Conclusion:

- suficiente para MVP de expected return simple
- insuficiente para forecasting serio por activo

### 6. Simulacion avanzada futura

#### Estado de datos: insuficiente por ahora

Brechas principales:

- covarianza robusta por activo
- series limpias y largas por instrumento
- betas/factores calibrados
- distribuciones de shocks consistentes
- supuestos de correlacion defendibles

Conclusion:

- fuera del MVP
- no debe iniciarse en esta fase

## Supuestos permitidos por modulo

### Risk Contribution

Permitido:

- volatilidad proxy por activo o bucket
- liquidez con contribucion casi nula
- confidence degradado cuando falte historia

No permitido:

- presentar el score como contribucion marginal exacta de varianza

### Scenario Analysis

Permitido:

- shocks cerrados y reglas heuristicas
- impacto nulo o reducido sobre liquidez y cash management

No permitido:

- escenarios abiertos pseudo-calibrados sin base estadistica

### Factor Exposure Proxy

Permitido:

- mappings heuristicos y `unknown`

No permitido:

- forzar clasificacion total de activos sin confianza

### Stress Testing

Permitido:

- escenarios extremos discretos y score de fragilidad

No permitido:

- inferencia probabilistica fuerte

### Expected Return Simple

Permitido:

- referencias estructurales por bucket o benchmark

No permitido:

- precision decimal pseudo-cientifica o narrativa de forecasting fino

## Riesgos operativos que afectan todos los modulos

### 1. Historia insuficiente de snapshots

Impacta principalmente:

- volatilidad proxy
- expected return contextual
- stress con apoyo temporal

Mitigacion MVP:

- warnings explicitos
- confidence `low`
- fallback documentado

### 2. Metadata faltante o inconsistente

Impacta principalmente:

- agrupacion por sector/pais
- factor exposure proxy
- scenario analysis

Mitigacion MVP:

- `unknown`
- flags de calidad de datos
- no imputar forzadamente categorias si no hay base razonable

### 3. Dependencia de proxies externos

Impacta principalmente:

- bonos AR via EMB
- liquidez via BADLAR
- expected return simple

Mitigacion MVP:

- exponer `methodology`, `data_basis`, `limitations` y `warnings`

## Decision final de viabilidad por modulo

| Modulo | Viabilidad MVP | Nivel de confianza | Nota |
|---|---|---:|---|
| Risk Contribution | Si | Media | Requiere volatilidad proxy y buen tagging |
| Scenario Analysis | Si | Media | Heuristico y cerrado |
| Factor Exposure Proxy | Si | Media-baja | Mappings y `unknown` son clave |
| Stress Testing ampliado | Si | Media | Reutiliza motor existente con extension controlada |
| Expected Return Simple | Si | Media-baja | Debe ser orientativo, no predictivo |
| Simulacion avanzada | No | Baja | Fuera de alcance y sin base suficiente |

## Recomendaciones para la siguiente fase

1. cerrar el MVP formal de Analytics v2 antes de crear codigo nuevo
2. empezar por `risk contribution`, porque usa mejor los datos actuales y agrega valor rapido
3. disenar `factor exposure proxy` con politica estricta de `unknown`
4. mantener `scenario analysis` y `stress testing` como motores heuristicos explicables
5. retrasar cualquier modelo avanzado hasta validar continuidad de snapshots y calidad de metadata
