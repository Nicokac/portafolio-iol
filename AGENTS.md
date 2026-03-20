# AGENTS.md

## Propósito

Este documento define cómo debe trabajar el agente sobre **Portfolio Analytics v2** dentro del proyecto de análisis de portafolio.

El objetivo no es producir cambios aislados, sino avanzar de forma controlada, modular, testeable y compatible con la arquitectura actual del sistema.

El agente debe priorizar:

* reutilización de código existente
* compatibilidad con v1
* servicios puros y tipados
* cobertura de tests
* entregas modulares y trazables
* bajo acoplamiento
* avance por confirmación humana entre módulos

---

## Contexto funcional del proyecto

La aplicación actual ya funciona como herramienta real de análisis del portafolio y soporta decisiones de inversión reales.

Capacidades actuales ya existentes:

* resumen diario del portafolio
* estrategia y composición
* análisis de concentración
* centro de performance
* centro de métricas analíticas
* planeación con recomendaciones y rebalanceo
* benchmark compuesto
* snapshots históricos
* servicios de métricas y riesgo

Benchmark compuesto actual:

* CEDEAR USA → SPY
* Bonos argentinos → EMB
* Liquidez ARS → BADLAR

Analytics v2 debe expandir la capacidad analítica actual, llevando el sistema desde análisis descriptivo a análisis explicativo, de sensibilidad y de soporte más avanzado para decisiones de inversión.

---

## Objetivo general de Analytics v2

Construir una segunda capa analítica que permita:

1. explicar mejor de dónde viene el riesgo del portafolio
2. estimar sensibilidad ante escenarios y shocks
3. medir exposición a factores de inversión
4. fortalecer recomendaciones y rebalanceos con señales más profundas
5. preparar el terreno para simulación avanzada futura

---

## Reglas operativas obligatorias para el agente

### 1. Regla de verificación previa

Antes de crear cualquier archivo, función, clase, servicio, schema, helper, fixture, vista o test, el agente debe:

1. inspeccionar la arquitectura actual
2. buscar si ya existe algo equivalente o reutilizable
3. verificar si puede extenderse en lugar de duplicarse
4. documentar en su respuesta qué encontró y qué va a reutilizar

El agente **no debe crear duplicados funcionales** si ya existe una implementación razonablemente reutilizable.

### 2. Regla de reutilización

Si ya existe lógica útil en el proyecto, el agente debe preferir este orden:

1. reutilizar sin cambios
2. reutilizar con extensión mínima
3. refactorizar con impacto controlado
4. crear nuevo componente solo si realmente no existe alternativa razonable

### 3. Regla de trabajo modular

El agente debe trabajar **por módulos completos**, no por cambios dispersos.

Eso implica:

* elegir un único módulo activo
* diseñarlo
* implementarlo
* testearlo
* documentarlo
* dejarlo listo
* detenerse y esperar confirmación humana antes de avanzar al siguiente módulo

### 4. Regla de no avance automático

Al terminar un módulo, el agente debe:

* resumir lo realizado
* listar archivos tocados
* listar tests agregados
* listar decisiones técnicas
* listar deuda pendiente del módulo si existiera
* proponer el mensaje de commit
* **esperar confirmación explícita** antes de seguir

### 5. Regla de tests obligatorios

Por cada nueva función creada o modificada, el agente debe evaluar si requiere test nuevo o ajuste de tests existentes.

Como política general:

* cada función nueva relevante debe tener al menos un test directo
* cada algoritmo central debe tener tests de comportamiento
* cada edge case importante debe tener cobertura
* cada contract/schema nuevo debe tener validación

Si una función no tiene test, el agente debe justificarlo explícitamente.

### 6. Regla de compatibilidad con v1

Analytics v2 no debe romper funcionalidades actuales.

El agente debe:

* evitar cambios destructivos sobre servicios actuales sin necesidad real
* preferir integrar v2 como capa nueva o extensible
* aislar contratos nuevos
* mantener trazabilidad de cualquier cambio compartido

### 7. Regla de pureza y desacoplamiento

El agente debe priorizar:

* servicios puros o casi puros
* separación entre cálculo y rendering
* separación entre lógica de dominio y presentación
* inputs explícitos
* outputs serializables
* bajo acoplamiento con vistas/templates

### 8. Regla de commits

Al cierre de cada módulo el agente debe proponer un mensaje de commit siguiendo la **misma estructura que los commits previos del proyecto**.

Dado que el repositorio usa mensajes en español, el agente debe redactarlos en español.

Hasta que se le indique otra convención exacta, debe usar un formato conservador y consistente como:

```text
feat(analytics-v2): agrega módulo de risk contribution MVP
```

O, si corresponde:

```text
refactor(analytics-v2): reutiliza helpers existentes para escenarios
```

```text
test(analytics-v2): agrega cobertura para factor exposure proxy
```

Si el proyecto ya muestra una estructura más específica, el agente debe detectarla y replicarla.

### 8.1. Regla operativa de Git

El agente puede ejecutar operaciones Git de cierre de trabajo, pero solo bajo estas condiciones:

* puede ejecutar `git add`
* puede ejecutar `git commit`
* puede ejecutar `git push`
* el push está permitido **solo** hacia la rama `develop`
* antes de ejecutar cualquiera de estas acciones debe existir confirmaci?n humana expl?cita
* para estas acciones, una respuesta del usuario de solo `Si` es confirmaci?n suficiente

Restricciones:

* no hacer push a ramas distintas de `develop`
* no hacer push si no hubo confirmaci?n expl?cita del usuario
* no usar esta regla para saltear la revisi?n y cierre de m?dulo

### 9. Regla de trazabilidad

Toda propuesta debe indicar:

* problema que resuelve
* módulo afectado
* dependencias
* archivos a tocar
* riesgos
* criterios de aceptación

### 10. Regla de no sobrediseño

El agente no debe saltar a modelos complejos si el roadmap todavía está en MVP.

Evitar adelantar:

* Monte Carlo avanzado
* optimización de frontera eficiente
* covarianza compleja
* betas sofisticadas
* calibraciones macro avanzadas

hasta que el roadmap lo habilite.

---

## Flujo de trabajo esperado del agente para cada módulo

Para cada módulo, el agente debe seguir este flujo exacto:

1. inspección de código existente
2. identificación de piezas reutilizables
3. diseño técnico del módulo
4. definición o ajuste de contratos/schemas
5. implementación backend
6. tests unitarios y de edge cases
7. documentación breve del módulo
8. resumen de cierre del módulo
9. propuesta de commit
10. espera de confirmación humana

---

## Roadmap general de Analytics v2

El roadmap está dividido en fases, módulos y submódulos.

---

# FASE 0 — Descubrimiento, especificación y alcance

## Objetivo

Definir Analytics v2 antes de implementar código nuevo.

## Resultado esperado

Que exista una base documental y técnica suficiente para que cualquier implementación posterior sea consistente, trazable y compatible con la arquitectura actual.

## Módulo 0.1 — Auditoría de arquitectura existente

### Objetivo

Inspeccionar el proyecto actual y mapear qué ya existe.

### Submódulos

#### 0.1.1 — Inventario de servicios actuales

Relevar:

* servicios de métricas
* servicios de riesgo
* servicios de benchmark
* servicios de snapshots históricos
* servicios de recomendaciones
* servicios de rebalanceo
* schemas, DTOs, serializers o estructuras equivalentes
* helpers compartidos

#### 0.1.2 — Inventario de datos disponibles

Relevar:

* posiciones actuales
* liquidez
* clasificaciones por activo
* datos sectoriales
* datos geográficos
* series históricas
* snapshots
* datos de performance
* benchmarks

#### 0.1.3 — Inventario de tests existentes

Relevar:

* tests de servicios
* fixtures de portafolio
* mocks de API
* datos sintéticos reutilizables

### Entregables esperados

* mapa de servicios existentes
* mapa de datos disponibles
* mapa de tests reutilizables

### Criterio de cierre

El agente debe poder responder qué existe, qué puede reutilizar y qué brechas reales hay.

---

## Módulo 0.2 — Especificación funcional de Analytics v2

### Objetivo

Definir con precisión qué es Analytics v2 y qué no es.

### Submódulos

#### 0.2.1 — Objetivos funcionales

Definir:

* mejor explicación del riesgo
* sensibilidad a escenarios
* exposición a factores
* mejora de recomendaciones
* preparación para simulación futura

#### 0.2.2 — Alcance inicial

Incluir explícitamente:

* risk contribution
* scenario analysis
* factor exposure proxy
* stress testing
* expected return simple como fase futura cercana
* simulación avanzada como fase posterior

#### 0.2.3 — Fuera de alcance inicial

Excluir explícitamente:

* optimización avanzada
* Monte Carlo complejo
* covariance engine completo
* factor models sofisticados
* frontier optimization

### Entregables esperados

* `docs/portfolio_analytics_v2_spec.md`

---

## Módulo 0.3 — Arquitectura técnica v2

### Objetivo

Definir cómo se integra v2 al proyecto sin romper v1.

### Submódulos

#### 0.3.1 — Estructura de carpetas

Definir ubicación de:

* servicios analytics_v2
* schemas
* adapters
* tests
* fixtures
* documentación técnica

#### 0.3.2 — Contratos de entrada y salida

Definir:

* inputs comunes
* outputs serializables
* naming consistente
* manejo de faltantes de datos

#### 0.3.3 — Integración con dashboard y recomendaciones

Definir puntos de consumo, no implementación final.

### Entregables esperados

* `docs/analytics_v2_architecture.md`
* `docs/analytics_v2_data_contracts.md`

---

## Módulo 0.4 — Gap analysis de datos

### Objetivo

Determinar si los datos actuales alcanzan para cada módulo.

### Submódulos

#### 0.4.1 — Brechas por módulo

Evaluar para:

* risk contribution
* scenario analysis
* factor exposure
* stress testing
* expected return
* simulation futura

#### 0.4.2 — Supuestos permitidos

Documentar proxys y fallback válidos.

### Entregables esperados

* `docs/analytics_v2_gap_analysis.md`

---

## Módulo 0.5 — Definición del MVP

### Objetivo

Cerrar alcance del primer release útil de Analytics v2.

### Submódulos

#### 0.5.1 — Priorización

Ordenar implementación:

1. risk contribution
2. scenario analysis
3. factor exposure proxy
4. stress testing
5. expected return simple
6. simulación avanzada posterior

#### 0.5.2 — Criterios de aceptación por módulo

Definir qué debe cumplirse para considerar cada módulo terminado.

### Entregables esperados

* `docs/analytics_v2_mvp.md`

---

# FASE 1 — Fundaciones técnicas compartidas

## Objetivo

Crear la base técnica común para todos los módulos de Analytics v2.

## Módulo 1.1 — Schemas y contratos compartidos

### Objetivo

Definir estructuras estables y reutilizables.

### Submódulos

#### 1.1.1 — Schemas comunes de portafolio

Ejemplos posibles:

* posición normalizada
* peso relativo
* clasificación por activo
* clasificación por país
* clasificación por sector
* liquidez normalizada

#### 1.1.2 — Schemas de resultados analíticos

Ejemplos posibles:

* item de risk contribution
* item de scenario impact
* item de factor exposure
* item de stress result
* metadata de calidad de datos

#### 1.1.3 — Validaciones y serialización

Definir contratos para consumo por dashboard y recomendaciones.

### Criterios de aceptación

* tipos claros
* naming consistente
* reutilización máxima de estructuras existentes
* tests para cada schema/validator relevante

---

## Módulo 1.2 — Helpers compartidos

### Objetivo

Centralizar lógica reutilizable transversal.

### Submódulos

#### 1.2.1 — Helpers de normalización

* pesos
* porcentajes
* totales
* rankings

#### 1.2.2 — Helpers de agrupación

* por sector
* por país
* por tipo de activo
* por moneda

#### 1.2.3 — Helpers de fallback y calidad de datos

* valores faltantes
* proxys válidos
* flags de confianza

### Criterios de aceptación

* sin duplicación de lógica
* tests por helper nuevo
* documentación breve del comportamiento

---

# FASE 2 — Módulo MVP 1: Risk Contribution

## Objetivo general

Responder:

> ¿Qué posiciones explican la mayor parte del riesgo del portafolio?

## Alcance MVP

Versión inicial basada en peso y volatilidad proxy, sin covarianza avanzada.

---

## Módulo 2.1 — Diseño del algoritmo de risk contribution

### Submódulos

#### 2.1.1 — Definición del score de riesgo MVP

Modelo inicial sugerido:

* `risk_score = peso * volatilidad_proxy`
* `contribution_pct = risk_score / suma_risk_score`

#### 2.1.2 — Definición de volatilidad proxy

Orden de prioridad:

1. volatilidad histórica disponible
2. volatilidad derivada de snapshots
3. volatilidad proxy por tipo de activo
4. fallback documentado

#### 2.1.3 — Reglas para liquidez

* contribución baja o cero
* comportamiento explícito en tests

---

## Módulo 2.2 — Implementación por activo

### Resultado esperado

Salida por instrumento con:

* símbolo
* tipo de activo
* peso
* volatilidad proxy
* risk score
* contribution pct
* flags de calidad de datos

### Criterios de aceptación

* suma de contribuciones ≈ 100%
* portafolio vacío no rompe
* faltantes usan fallback controlado
* tests unitarios completos

---

## Módulo 2.3 — Agregación por sector y país

### Resultado esperado

Agrupación de contribución al riesgo por:

* sector
* país
* tipo de activo

### Criterios de aceptación

* consistencia entre agregados y detalle
* tests de agrupación

---

## Módulo 2.4 — Señales para recomendaciones

### Resultado esperado

Flags como:

* riesgo concentrado en pocos activos
* riesgo concentrado en tech
* riesgo concentrado en Argentina
* divergencia entre concentración patrimonial y concentración de riesgo

### Criterios de aceptación

* outputs reutilizables por el motor de recomendaciones
* trazabilidad del origen de la señal

---

## Módulo 2.5 — Tests del módulo

### Cobertura mínima esperada

* caso base
* portafolio vacío
* activo sin volatilidad histórica
* liquidez presente
* agregación por sector
* agregación por país
* suma de contribuciones
* orden de top contributors

---

## Cierre del módulo

Al finalizar, el agente debe detenerse y esperar confirmación humana.

Commit esperado, ejemplo:

```text
feat(analytics-v2): agrega módulo de risk contribution MVP
```

---

# FASE 3 — Módulo MVP 2: Scenario Analysis

## Objetivo general

Responder:

> ¿Qué pasa con el portafolio si ocurre un shock específico?

---

## Módulo 3.1 — Catálogo de escenarios MVP

### Escenarios iniciales sugeridos

* caída SPY -10%
* caída SPY -20%
* shock tech
* stress Argentina
* devaluación ARS
* compresión emergentes
* suba de tasas USA

### Criterios de aceptación

* escenarios definidos en estructura reutilizable
* nombres consistentes
* posibilidad de extensión futura

---

## Módulo 3.2 — Motor de sensibilidad heurística

### Objetivo

Aplicar reglas iniciales por tipo de activo, país, sector y moneda.

### Submódulos

#### 3.2.1 — Sensibilidad por clase de activo

#### 3.2.2 — Sensibilidad por sector

#### 3.2.3 — Sensibilidad por geografía

#### 3.2.4 — Sensibilidad por moneda

### Criterios de aceptación

* reglas trazables
* documentadas
* cubiertas por tests

---

## Módulo 3.3 — Cálculo de impacto

### Resultado esperado

Para cada escenario:

* impacto estimado total
* impacto por activo
* impacto por sector
* impacto por país
* peor contribuidor

### Criterios de aceptación

* outputs serializables
* consistencia matemática básica
* tests por escenario clave

---

## Módulo 3.4 — Integración con alertas y planeación

### Resultado esperado

Señales como:

* vulnerabilidad alta a shock tech
* vulnerabilidad alta a Argentina
* amortiguación por liquidez

---

## Módulo 3.5 — Tests del módulo

### Cobertura mínima esperada

* shock válido
* shock inválido
* liquidez sin shock indebido
* activos tech afectados más que defensivos
* stress Argentina afecta instrumentos locales
* devaluación impacta exposición relevante

---

## Cierre del módulo

El agente debe detenerse y esperar confirmación.

Commit esperado, ejemplo:

```text
feat(analytics-v2): agrega módulo de scenario analysis MVP
```

---

# FASE 4 — Módulo MVP 3: Factor Exposure Proxy

## Objetivo general

Responder:

> ¿A qué factores o estilos está expuesto el portafolio?

---

## Módulo 4.1 — Modelo de factores MVP

### Factores iniciales sugeridos

* growth
* value
* quality
* dividend
* defensive
* cyclical

### Criterios de aceptación

* lista cerrada inicial
* definición documentada de cada factor

---

## Módulo 4.2 — Clasificación proxy por activo

### Objetivo

Etiquetar activos usando reglas heurísticas o mapping controlado.

### Submódulos

#### 4.2.1 — Mapa explícito por símbolo cuando sea necesario

#### 4.2.2 — Fallback por tipo de activo o sector

#### 4.2.3 — Clasificación `unknown` para activos sin etiqueta confiable

### Criterios de aceptación

* trazabilidad de clasificación
* tests de mapping y fallback

---

## Módulo 4.3 — Agregación de exposición factorial

### Resultado esperado

* exposición por factor
* factor dominante
* factores subrepresentados
* contribuyentes principales por factor

### Criterios de aceptación

* consistencia con pesos
* serialización clara
* tests de agregación

---

## Módulo 4.4 — Señales para recomendaciones

### Resultado esperado

Señales como:

* exceso de growth
* falta de defensive
* falta de dividend
* concentración factorial excesiva

---

## Módulo 4.5 — Tests del módulo

### Cobertura mínima esperada

* clasificación básica de activos conocidos
* fallback para activos no mapeados
* unknown cuando no hay certeza
* agregación por factor
* consistencia de totales

---

## Cierre del módulo

El agente debe detenerse y esperar confirmación.

Commit esperado, ejemplo:

```text
feat(analytics-v2): agrega módulo de factor exposure proxy
```

---

# FASE 5 — Módulo MVP 4: Stress Testing

## Objetivo general

Responder:

> ¿Qué tan frágil es el portafolio ante eventos extremos?

---

## Módulo 5.1 — Definición de stresses extremos

### Ejemplos iniciales

* crash USA severo
* crisis local severa
* doble shock tasas + equities
* deterioro emergente

---

## Módulo 5.2 — Motor de stress

### Resultado esperado

* pérdida estimada total
* activos más vulnerables
* sectores más vulnerables
* score de fragilidad del portafolio

---

## Módulo 5.3 — Integración con recomendaciones

### Resultado esperado

Señales como:

* fragilidad alta ante crisis local
* fragilidad alta ante concentración sectorial
* liquidez insuficiente como amortiguador

---

## Módulo 5.4 — Tests del módulo

### Cobertura mínima esperada

* aplicación correcta de stress extremo
* consistencia de pérdidas
* ranking de vulnerabilidad
* manejo de portafolio mixto con liquidez

---

## Cierre del módulo

El agente debe detenerse y esperar confirmación.

Commit esperado, ejemplo:

```text
feat(analytics-v2): agrega módulo de stress testing MVP
```

---

# FASE 6 — Módulo MVP 5: Expected Return Simple

## Objetivo general

Agregar una primera estimación simple de retorno esperado, controlada y explicable.

---

## Módulo 6.1 — Modelo simple de retorno esperado

### Posibles enfoques

* baseline por benchmark asociado
* baseline por asset class
* baseline real vs inflación / BADLAR

### Restricción

Debe ser explicable y no pseudo-científico.

---

## Módulo 6.2 — Integración con planeación

### Resultado esperado

Señales como:

* portafolio con baja expectativa real
* liquidez excedente con retorno esperado inferior a benchmark objetivo

---

## Módulo 6.3 — Tests del módulo

### Cobertura mínima esperada

* asignación correcta por clase de activo
* outputs válidos
* faltantes con fallback explícito

---

## Cierre del módulo

El agente debe detenerse y esperar confirmación.

Commit esperado, ejemplo:

```text
feat(analytics-v2): agrega módulo de expected return simple
```

---

# FASE 7 — Integración gradual con producto

## Objetivo

Consumir los módulos v2 en la aplicación sin romper UX ni arquitectura.

## Módulo 7.1 — Integración con dashboard

### Submódulos

#### 7.1.1 — Nueva sección Analytics v2

#### 7.1.2 — Tarjetas resumen por módulo

#### 7.1.3 — Tablas y gráficos por módulo

#### 7.1.4 — Tooltips metodológicos

#### 7.1.5 — Badges de calidad de datos

### Criterios de aceptación

* sin mezcla indebida con lógica de cálculo
* front consume outputs ya preparados
* tests de integración si aplica

---

## Módulo 7.2 — Integración con motor de recomendaciones

### Submódulos

#### 7.2.1 — Señales de risk contribution

#### 7.2.2 — Señales de scenario analysis

#### 7.2.3 — Señales de factor exposure

#### 7.2.4 — Señales de stress testing

#### 7.2.5 — Priorización de recomendaciones

### Criterios de aceptación

* recomendaciones trazables
* sin duplicar lógica de cálculo
* tests de integración o contract tests

---

## Cierre de fase

El agente debe detenerse y esperar confirmación antes de pasar a una integración mayor o refactors cruzados.

---

# FASE 8 — Evolución avanzada posterior al MVP

## Objetivo

Expandir Analytics v2 solo después de validar valor del MVP.

## Módulos futuros posibles

* covariance-aware risk contribution
* factor model más robusto
* betas por benchmark
* Monte Carlo
* efficient frontier
* optimización de rebalanceo con restricciones
* scenario engine parametrizable por usuario

## Restricción

No iniciar esta fase sin aprobación explícita.

---

## Orden operativo recomendado de ejecución

El agente debe respetar este orden salvo instrucción explícita en contrario:

1. Fase 0 completa
2. Fase 1 completa
3. Módulo Risk Contribution
4. esperar confirmación
5. Módulo Scenario Analysis
6. esperar confirmación
7. Módulo Factor Exposure Proxy
8. esperar confirmación
9. Módulo Stress Testing
10. esperar confirmación
11. Módulo Expected Return Simple
12. esperar confirmación
13. Integración con dashboard
14. esperar confirmación
15. Integración con recomendaciones
16. esperar confirmación
17. Fase avanzada solo con autorización explícita

---

## Definición de “módulo terminado”

Un módulo se considera terminado solo si cumple todos estos puntos:

1. inspección previa realizada
2. reutilización evaluada y aplicada donde corresponda
3. implementación completada
4. tests agregados y ejecutados
5. edge cases cubiertos
6. documentación breve agregada o actualizada
7. salida serializable y consistente
8. resumen de cierre preparado
9. mensaje de commit propuesto
10. espera de confirmación humana

---

## Formato obligatorio de cierre de módulo

Al cerrar cada módulo, el agente debe responder con este esquema:

### 1. Módulo finalizado

Nombre del módulo.

### 2. Qué se hizo

Resumen breve y concreto.

### 3. Reutilización detectada

Qué ya existía y cómo se reutilizó.

### 4. Archivos creados o modificados

Lista clara.

### 5. Tests agregados o actualizados

Lista clara.

### 6. Edge cases cubiertos

Lista clara.

### 7. Limitaciones actuales

Qué queda deliberadamente fuera del MVP.

### 8. Commit propuesto

Mensaje de commit en español siguiendo la convención detectada.

### 9. Próximo módulo sugerido

Solo sugerido, no ejecutado.

### 10. Estado

Esperando confirmación para avanzar.

---

## Política de testing

### Reglas mínimas

* cada función nueva relevante debe tener test nuevo
* cada bugfix debe venir acompañado por test de regresión si aplica
* cada helper compartido nuevo debe tener tests propios
* cada output agregado debe tener validación básica
* los tests deben ser legibles y orientados a comportamiento

### Edge cases a considerar siempre

* portafolio vacío
* una sola posición
* alta liquidez
* datos faltantes
* clasificación desconocida
* valores cero
* divisiones por cero
* activos sin histórico suficiente

---

## Política de documentación

El agente debe documentar en forma breve y útil:

* objetivo del módulo
* inputs
* outputs
* algoritmo MVP
* limitaciones
* futuros puntos de extensión

Debe evitar documentación inflada o redundante.

---

## Política de refactor

El agente puede refactorizar solo si:

* mejora reutilización
* reduce duplicación real
* no rompe compatibilidad sin justificación
* está acotado al módulo activo o a una dependencia inmediata

Si detecta un refactor mayor, debe proponerlo y esperar aprobación.

---

## Instrucción final para el agente

Trabajá como un desarrollador senior orientado a arquitectura y entregas controladas.

No avances por cantidad de archivos ni por velocidad.
Avanzá por módulos terminados, testeados y confirmados.

Antes de crear, verificá.
Antes de duplicar, reutilizá.
Antes de avanzar, cerrá.
Antes del siguiente módulo, esperá confirmación.
