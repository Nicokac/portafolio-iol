# Diagrama de Arquitectura

```mermaid
flowchart LR
    IOL[IOL API] --> SYNC[IOL Sync Service]
    SYNC --> DB[(PostgreSQL/SQLite)]
    SYNC --> REDIS[(Redis)]
    REDIS --> CELERY[Celery Worker/Beat]
    DB --> ANALYTICS[Analytics Services]
    ANALYTICS --> API[Internal API - DRF]
    ANALYTICS --> DASH[Dashboard Django Templates]
    API --> DASH
```

## Componentes
- `IOL API`: fuente externa de datos operativos.
- `IOL Sync Service`: sincronizacion de cuentas, portafolio y operaciones.
- `Database`: snapshots y metadata persistente.
- `Analytics Services`: riesgo, performance, attribution, liquidez, calidad de datos.
- `Internal API`: expone metrica y capacidades para UI y consumo interno.
- `Dashboard`: visualizacion de KPIs, alertas y soporte de decisiones.
