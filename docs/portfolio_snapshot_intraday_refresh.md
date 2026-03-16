# Refresco intradia de PortfolioSnapshot

## Objetivo

Permitir que el snapshot diario del portafolio se refresque dentro del mismo dia cuando el usuario primero sincroniza IOL y luego vuelve a consolidar el snapshot.

## Cambio aplicado

- `PortfolioSnapshot` sigue siendo unico por `fecha`
- si ya existe un snapshot del dia:
  - se actualizan sus campos patrimoniales
  - se recrean sus `PositionSnapshot`
  - se conserva el mismo registro diario
- la trazabilidad del ultimo refresco se toma desde `updated_at`

## Implicancia operativa

El orden correcto para uso manual queda:

1. `Actualizar IOL`
2. `Generar Snapshot`

Si se vuelve a ejecutar `Generar Snapshot` el mismo dia, el snapshot ya no queda congelado: se refresca.

## UI

Los bloques que antes mostraban solo la fecha del ultimo snapshot ahora muestran fecha y hora del ultimo refresh cuando esa informacion existe.

## Limitaciones

- no guarda multiples versiones intradia del mismo dia
- no reemplaza una auditoria completa de diferencias entre refreshes
- la trazabilidad fina sigue siendo por `updated_at`, no por versionado historico
