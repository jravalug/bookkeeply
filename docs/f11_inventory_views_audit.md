# F11.1 - Auditoria de vistas de inventario y consumo

Fecha: 2026-03-10
Estado: completado (auditoria inicial)

## 1) Alcance revisado

### Rutas web inventario/reportes impactadas

- app/routes/inventory.py
  - GET/POST /inventory/item/list
  - GET /inventory/accounting/manage
- app/routes/reports.py
  - GET/POST /report/inventory-consumption/view

### Templates auditados

- app/templates/inventory/item_list.html
- app/templates/inventory/accounting_manage.html
- app/templates/report/inventory_consumption.html

## 2) Hallazgos UX/UI

1. Formularios full-page y refresh completo en acciones frecuentes.

- item_list usa POST tradicional para alta/edicion; no hay swaps parciales.
- accounting_manage usa POST + redirect para adoptar/desadoptar cuentas.

1. Estructura repetitiva y baja reutilizacion de bloques.

- item_list mezcla formulario de alta, tabla y formulario inline de edicion en un solo template.
- inventory_consumption incluye formulario de filtro, tabla por dia y exportacion en una misma vista sin partials.

1. Patrones visuales heterogeneos.

- inventory_consumption usa formato por bloques diarios; item_list y accounting_manage priorizan tablas planas.
- Hay consistencia de utilidades Tailwind, pero no de layout funcional por tarea.

1. Oportunidad clara de HTMX con fallback ya preparado por rutas POST.

- Las rutas actuales permiten introducir fragmentos sin romper el flujo tradicional.

## 3) Matriz de refactor para F11

| Vista | Estado propuesto | Accion |
| --- | --- | --- |
| app/templates/inventory/item_list.html | Mantener + refactor | Extraer partials de alta y tabla; habilitar alta/edicion con HTMX por fila. |
| app/templates/inventory/accounting_manage.html | Mantener + refactor | Extraer tabla de cuentas y tabla de auditoria; adopcion/desadopcion con swap parcial. |
| app/templates/report/inventory_consumption.html | Mantener + refactor | Separar filtro, resultados y export; aplicar HTMX al filtro de mes. |

## 4) Partials recomendados

- app/templates/inventory/partials/_item_form.html
- app/templates/inventory/partials/_item_table.html
- app/templates/inventory/partials/_account_catalog_table.html
- app/templates/inventory/partials/_account_audit_table.html
- app/templates/report/partials/_inventory_consumption_filter.html
- app/templates/report/partials/_inventory_consumption_results.html

## 5) Secuencia sugerida de ejecucion

1. Extraer partials sin cambiar comportamiento (fase de seguridad).
2. Introducir HTMX en alta/edicion de inventario y adopcion de cuentas.
3. Introducir HTMX en filtro de consumo mensual.
4. Mantener fallback POST/redirect en todas las acciones.

## 6) Criterios de salida de esta auditoria

- Vistas inventario/consumo relevadas y trazadas a rutas reales.
- Hallazgos priorizados para F11.2/F11.3.
- Lista concreta de partials para implementacion incremental.

## 7) Implementacion asociada (F11.2)

- Se extrajeron partials en inventario:
  - app/templates/inventory/partials/_item_form.html
  - app/templates/inventory/partials/_item_table.html
  - app/templates/inventory/partials/_account_catalog_table.html
  - app/templates/inventory/partials/_account_audit_table.html
- Se extrajeron partials en reportes:
  - app/templates/report/partials/_inventory_consumption_filter.html
  - app/templates/report/partials/_inventory_consumption_results.html
- Se actualizaron vistas principales para consumir los partials sin cambio de comportamiento:
  - app/templates/inventory/item_list.html
  - app/templates/inventory/accounting_manage.html
  - app/templates/report/inventory_consumption.html
- Validacion tecnica posterior al refactor:
  - pruebas focales de rutas/smoke: 5 tests OK
  - suite completa en webdev: 118 tests OK

## 8) Implementacion asociada (F11.3)

- Se agrego soporte HTMX en rutas:
  - `app/routes/inventory.py`
    - `item_list`: en `HX-Request` retorna `inventory/partials/_item_panel.html` con mensaje inline.
    - `item_update`: en `HX-Request` retorna panel actualizado sin redirect.
    - `accounting_manage`: en `HX-Request` retorna `inventory/partials/_accounting_manage_content.html`.
  - `app/routes/reports.py`
    - `inventory_consumption_view`: en `HX-Request` retorna `report/partials/_inventory_consumption_content.html`.
- Se agregaron atributos `hx-post/hx-target/hx-swap` en formularios de:
  - alta/edicion de inventario,
  - adopcion/desadopcion contable,
  - filtro mensual de consumo de inventario.
- Se ajusto el script de exportacion de consumo para funcionar tras swaps HTMX.
- Pruebas agregadas/actualizadas:
  - `tests/routes/test_inventory_item_list_htmx.py`
  - `tests/routes/test_reports_inventory_consumption_view_htmx.py`
  - `tests/routes/test_inventory_accounting_manage_view.py` (caso HTMX)
- Validacion tecnica F11.3:
  - pruebas focales: 8 tests OK
  - suite completa en webdev: 122 tests OK

## 9) Cierre F11 (fallback clasico + consistencia visual)

- Fallback clasico validado (sin encabezado `HX-Request`):
  - `POST /inventory/item/list` mantiene `302` y flujo tradicional.
  - `POST /report/inventory-consumption/view` mantiene render completo server-side.
- Checklist de consistencia visual minima automatizada:
  - `item_list` incluye panel unico `inventory/partials/_item_panel.html`.
  - `accounting_manage` incluye panel unico `inventory/partials/_accounting_manage_content.html`.
  - `inventory_consumption` incluye panel unico `report/partials/_inventory_consumption_content.html`.
- Pruebas agregadas para cierre:
  - `tests/routes/test_inventory_ui_consistency_check.py`
  - ampliaciones de fallback en:
    - `tests/routes/test_inventory_item_list_htmx.py`
    - `tests/routes/test_reports_inventory_consumption_view_htmx.py`
- Validacion final de cierre F11:
  - focales: 11 tests OK
  - suite completa en webdev: 127 tests OK
