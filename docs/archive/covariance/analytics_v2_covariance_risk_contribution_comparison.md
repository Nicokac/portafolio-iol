# Validacion comparativa: MVP vs covariance-aware risk contribution

## Objetivo

Comparar en casos sinteticos controlados cuando la variante `covariance_aware` cambia realmente la lectura del riesgo frente al MVP `weight * volatility`.

## Casos validados

### 1. Cluster correlacionado

Cartera sintetica:

- AAPL
- MSFT
- BOND

Supuesto:

- mismo peso patrimonial
- misma volatilidad standalone en el MVP
- covarianza alta entre AAPL y MSFT
- baja covarianza del bono

Resultado esperado:

- el MVP reparte riesgo casi igual
- `covariance_aware` sube la contribucion de AAPL/MSFT
- `covariance_aware` baja la del bono diversificador

### 2. Caso diagonal

Cartera sintetica:

- AAPL
- MSFT
- BOND

Supuesto:

- misma volatilidad standalone
- matriz diagonal sin correlaciones relevantes

Resultado esperado:

- `covariance_aware` queda cerca del MVP
- no introduce una lectura artificialmente distinta

## Conclusion

La variante avanzada agrega valor cuando existe concentracion de riesgo por co-movimiento, no solo por peso y volatilidad standalone.

Si la matriz no agrega estructura de correlacion relevante, el resultado debe permanecer cercano al MVP.

## Decision operativa

Antes de exponer esta variante en producto conviene mantenerla como modulo tecnico y validar mas casos reales del portafolio.
