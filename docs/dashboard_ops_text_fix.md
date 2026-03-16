# Corrección de textos en hoja Ops

## Objetivo

Corregir textos visibles con problemas de encoding en la hoja `Ops / Observabilidad` sin tocar métricas, queries ni endpoints.

## Cambio aplicado

- normalización completa de `templates/dashboard/ops.html` a UTF-8
- preservación de:
  - tablas
  - ids de DOM
  - fetch AJAX
  - estructura de cards

## Alcance

- alert operativo
- encabezados
- labels de tablas
- textos de apoyo
- separadores visuales del bloque de observabilidad

## Limitaciones

- no corrige todavía otros templates con mojibake fuera de `Ops`
- no cambia lógica de observabilidad ni payloads API
