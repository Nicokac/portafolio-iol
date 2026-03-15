# Analytics v2 - Contratos de Datos

## Objetivo

Definir contratos de entrada y salida para Analytics v2 con foco en:

- inputs explicitos
- outputs serializables
- metadata metodologica
- manejo consistente de faltantes

Estos contratos no son todavia clases Python obligatorias.
Son la especificacion de forma que deben respetar los modulos de v2.

## Principios

Los contratos de v2 deben cumplir:

- serializacion simple a JSON
- nombres consistentes entre modulos
- metadata de metodologia y base de calculo
- flags de calidad de datos cuando corresponda
- ausencia de dependencias de UI

## Inputs comunes esperados

### 1. Posicion normalizada

Contrato logico:

```text
{
  symbol: str,
  description: str,
  market_value: float,
  weight_pct: float,
  sector: str | None,
  country: str | None,
  asset_type: str | None,
  strategic_bucket: str | None,
  patrimonial_type: str | None,
  currency: str | None,
  gain_pct: float | None,
  gain_money: float | None,
}
```

Fuente esperada:

- `ActivoPortafolioSnapshot`
- `ParametroActivo`
- o `PositionSnapshot` cuando aplique

### 2. Snapshot normalizado de portafolio

```text
{
  date: str,
  total_iol: float,
  liquidity_operativa: float,
  cash_management: float,
  invested_portfolio: float,
  usa_exposure_pct: float | None,
  argentina_exposure_pct: float | None,
}
```

Fuente esperada:

- `PortfolioSnapshot`

### 3. Metadata de benchmark disponible

```text
{
  benchmark_key: str,
  symbol: str,
  source: str,
  interval: str,
  observations: int,
  latest_date: str | None,
}
```

Fuente esperada:

- `BenchmarkSnapshot`
- `BenchmarkSeriesService`

### 4. Metadata de calidad de datos

```text
{
  has_missing_metadata: bool,
  has_insufficient_history: bool,
  used_fallback: bool,
  confidence: str,
  warnings: list[str],
}
```

## Metadata comun de salida

Todo output principal de v2 debe incluir una metadata base con esta forma logica:

```text
{
  methodology: str,
  data_basis: str,
  limitations: str,
  confidence: str,
  warnings: list[str],
}
```

Convenciones:

- `methodology`: explica el algoritmo MVP usado
- `data_basis`: base economica o patrimonial usada
- `limitations`: limites importantes del calculo
- `confidence`: `high`, `medium`, `low`
- `warnings`: lista de observaciones operativas o metodologicas

## Contratos por modulo

### 1. Risk Contribution

#### 1.1 Item por activo

```text
{
  symbol: str,
  weight_pct: float,
  volatility_proxy: float | None,
  risk_score: float,
  contribution_pct: float,
  sector: str | None,
  country: str | None,
  asset_type: str | None,
  used_volatility_fallback: bool,
}
```

#### 1.2 Resultado agregado

```text
{
  items: list[risk_contribution_item],
  by_sector: list[group_item],
  by_country: list[group_item],
  by_asset_type: list[group_item],
  top_contributors: list[risk_contribution_item],
  metadata: common_metadata,
}
```

#### 1.3 Contrato de grupo

```text
{
  key: str,
  contribution_pct: float,
  weight_pct: float | None,
}
```

### 2. Scenario Analysis

#### 2.1 Escenario solicitado

```text
{
  scenario_key: str,
  label: str,
  description: str,
}
```

#### 2.2 Impacto por activo

```text
{
  symbol: str,
  market_value: float,
  estimated_impact_pct: float,
  estimated_impact_money: float,
  transmission_channel: str,
}
```

#### 2.3 Resultado del escenario

```text
{
  scenario_key: str,
  total_impact_pct: float,
  total_impact_money: float,
  by_asset: list[scenario_asset_impact],
  by_sector: list[group_impact],
  by_country: list[group_impact],
  top_negative_contributors: list[scenario_asset_impact],
  metadata: common_metadata,
}
```

### 3. Factor Exposure Proxy

#### 3.1 Exposicion por factor

```text
{
  factor: str,
  exposure_pct: float,
  confidence: str,
}
```

#### 3.2 Resultado de factores

```text
{
  factors: list[factor_exposure_item],
  dominant_factor: str | None,
  underrepresented_factors: list[str],
  unknown_assets: list[str],
  metadata: common_metadata,
}
```

### 4. Stress Fragility

#### 4.1 Resultado de stress

```text
{
  scenario_key: str,
  fragility_score: float,
  total_loss_pct: float,
  total_loss_money: float,
  vulnerable_assets: list[scenario_asset_impact],
  vulnerable_sectors: list[group_impact],
  vulnerable_countries: list[group_impact],
  metadata: common_metadata,
}
```

### 5. Expected Return Simple

#### 5.1 Resultado esperado

```text
{
  expected_return_pct: float | None,
  real_expected_return_pct: float | None,
  basis_reference: str,
  by_bucket: list[expected_return_bucket_item],
  metadata: common_metadata,
}
```

#### 5.2 Bucket de retorno esperado

```text
{
  bucket: str,
  weight_pct: float,
  expected_return_pct: float | None,
  reference_used: str | None,
}
```

## Contratos de flags y faltantes

### Reglas comunes

Si un modulo no puede calcular una parte del resultado:

- no debe romper toda la respuesta si existe salida parcial util
- debe usar `None` en campos no calculables
- debe agregar warning explicito
- debe degradar `confidence`

### Ejemplos

#### Historia insuficiente

```text
{
  confidence: "low",
  warnings: ["insufficient_history"],
}
```

#### Metadata faltante

```text
{
  confidence: "medium",
  warnings: ["missing_asset_metadata"],
}
```

#### Uso de proxy

```text
{
  confidence: "medium",
  warnings: ["volatility_proxy_used"],
}
```

## Contratos para integracion con dashboard

Los consumidores de dashboard deben recibir payloads listos para presentacion.

Eso implica:

- porcentajes ya calculados
- labels auditables
- metadata separada del detalle
- sin necesidad de recalculo en templates

## Contratos para integracion con recomendaciones

Los motores de recomendacion y rebalanceo deben consumir senales estructuradas, no parsear texto libre.

Contrato logico sugerido para una senal:

```text
{
  signal_key: str,
  severity: str,
  title: str,
  description: str,
  affected_scope: str,
  evidence: dict,
}
```

Convenciones:

- `signal_key`: id estable
- `severity`: `low`, `medium`, `high`
- `affected_scope`: `portfolio`, `sector`, `country`, `asset`, `factor`
- `evidence`: payload chico con datos concretos

## Contratos para testing

Cada modulo debe tener tests que validen al menos:

- forma de salida
- serializacion
- manejo de `None`
- warnings esperados
- consistencia de sumas cuando aplique

## Compatibilidad con v1

Los contratos de Analytics v2 deben ser aditivos.

Esto implica:

- no romper endpoints actuales
- no renombrar payloads de v1 sin migracion explicita
- no mezclar contratos v2 dentro de servicios legacy sin necesidad justificada

## Estado

Documento base de contratos de datos para Analytics v2.
Listo para servir de referencia del siguiente modulo tecnico o del primer modulo funcional MVP.
