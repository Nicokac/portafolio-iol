# Monitoreo de continuidad diaria de snapshots

## Objetivo

Detectar si la historia que necesita `covariance_aware` esta creciendo de forma natural o si hay un corte operativo real.

## Inputs

- `ActivoPortafolioSnapshot`
- `ResumenCuentaSnapshot`
- `PortfolioSnapshot`
- auditoria diaria de historia util (`SnapshotHistoryAuditService`)

## Output

`DailySnapshotContinuityService.build_report()` devuelve:

- `rows` por fecha reciente
- `raw_snapshots_present`
- `account_snapshot_present`
- `portfolio_snapshot_present`
- `usable_for_covariance`
- `status` por fecha: `healthy`, `warning`, `broken`
- `overall_status`
- `status_counts`

## Regla de estados

- `healthy`: la fecha tiene raw snapshots, account snapshot, portfolio snapshot y ya es usable para covarianza
- `warning`: hay actividad parcial, pero la fecha todavia no es usable o falta alguna capa consolidada
- `broken`: la fecha no tiene fuentes operativas minimas

## Uso recomendado

- hoja staff `Ops`
- seguimiento diario de continuidad
- validacion de que la historia util crece sin intervencion manual

## Limitaciones

- no explica por si mismo por que fallo una tarea puntual
- no reemplaza auditorias de Celery, token o sync IOL
- usa el universo invertido actual, no reconstruye universos historicos
