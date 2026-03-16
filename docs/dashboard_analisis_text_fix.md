# Corrección de textos en hoja Análisis

## Objetivo

Corregir textos visibles con mojibake en la hoja `Análisis` sin tocar cálculos ni contratos del dashboard.

## Cambio aplicado

- normalización de literales visibles en `templates/dashboard/analisis.html`
- conservación total de:
  - estructura
  - gráficos
  - datos
  - tooltips

## Alcance

- título de página
- encabezados
- labels
- textos de apoyo
- tooltips

## Limitaciones

- no corrige todavía otros templates con problemas de encoding
- no cambia lógica analítica ni de presentación fuera de `Análisis`
