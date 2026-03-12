# Metodologia Financiera

Este documento define como se calculan las metricas del sistema Portafolio IOL.

## 1) Volatilidad
- Definicion: desvio estandar de retornos diarios del patrimonio total, anualizado.
- Formula: `vol_anual = std(r_t) * sqrt(252)`.
- Fuente: `PortfolioSnapshot.total_iol`.
- Limitacion: requiere al menos 2 observaciones, idealmente >= 30.

## 2) Time Weighted Return (TWR)
- Definicion: retorno compuesto neutralizando efecto de flujos externos.
- Uso: medir performance de cartera separada de aportes/retiros.
- Fuente: snapshots de patrimonio.
- Limitacion: calidad depende de granularidad de flujos disponibles.

## 3) VaR Historico
- Definicion: percentil de cola de los retornos historicos.
- Formula base: `VaR_95 = -percentile(returns, 5)`.
- Escalado: `VaR_h = VaR_1d * sqrt(h)`.
- Limitacion: asume que la historia reciente representa el futuro.

## 4) VaR Parametrico
- Definicion: VaR usando media y desvio con aproximacion normal.
- Formula: `VaR = -(mu_h + z_q * sigma_h)`.
- Limitacion: sensible a no normalidad y colas pesadas.

## 5) CVaR (Expected Shortfall)
- Definicion: perdida promedio condicionada a exceder VaR.
- Formula: `CVaR = -mean(r_t | r_t <= VaR_threshold)`.
- Limitacion: necesita suficiente muestra de cola.

## 6) Sharpe Ratio
- Definicion: retorno excedente por unidad de volatilidad total.
- Formula: `Sharpe = (E[r] - rf) / sigma`.
- Implementacion actual: version simplificada sobre retornos de snapshots.

## 7) Sortino Ratio
- Definicion: retorno excedente por unidad de volatilidad negativa.
- Formula: `Sortino = (E[r] - rf) / sigma_downside`.
- Limitacion: inestable con pocas observaciones negativas.

## 8) Tracking Error
- Definicion: volatilidad anualizada del retorno activo.
- Formula: `TE = std(r_port - r_bench) * sqrt(252)`.

## 9) Information Ratio
- Definicion: retorno activo promedio dividido por tracking error.
- Formula: `IR = mean(r_port - r_bench) / TE`.

## 10) Attribution de Performance
- Por activo: `contribution_i = weight_i * return_i`.
- Por bucket (sector/pais/tipo): suma de contribuciones de activos del bucket.
- Por flujos: descomposicion `total_return = market_return + flow_effect`.

## 11) Markowitz
- Inputs:
  - retornos esperados anualizados
  - matriz de covarianza anualizada
- Objetivo: minimizar varianza para retorno objetivo o aproximar max Sharpe.
- Restricciones: long-only y pesos normalizados.

## 12) Risk Parity
- Objetivo: balancear contribucion de riesgo entre activos.
- Implementacion actual: aproximacion inversa de volatilidad marginal.

## Convenciones
- Base principal de retorno/riesgo: `PortfolioSnapshot.total_iol`.
- Anualizacion: 252 dias habiles.
- Si hay historial insuficiente: se emite `warning=insufficient_history`.
