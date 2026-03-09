# Plan maestro de implementacion por fases (Inventory)

Fecha de actualizacion: 2026-03-09
Estado: propuesta contextualizada (ajustada con decisiones funcionales)

## 1) Proposito

Este archivo define el plan maestro para evolucionar el modulo de inventario hacia una operacion real de control de existencias, costos y trazabilidad, alineado con el mismo marco de ejecucion del plan de ingresos.

Objetivos globales:

1. Consolidar inventario como libro operacional auditable por negocio.
2. Separar catalogo, entradas, salidas, ajustes y valorizacion de stock.
3. Integrar consumo real desde ventas/recetas sin degradar rendimiento.
4. Entregar reportes de decision (rotacion, quiebres, costo de consumo, mermas).
5. Unificar UX de inventario con convenciones actuales (modales, partials y HTMX donde aporte).

## 2) Criterios de ejecucion

- Cambios por fase, sin mezclar entregables de fases futuras.
- Cada fase cierra con validacion tecnica (errores + smoke minimo).
- Toda tarea debe quedar marcada en este archivo (`[ ]` pendiente / `[x]` completada).
- Reglas de negocio y umbrales operativos deben ser configurables desde la aplicacion cuando aplique.

## 2.1) Contexto pais (Cuba)

Este plan se ejecuta bajo contexto operativo y fiscal de Cuba. La implementacion debe respetar:

- Operacion monetaria principal en `CUP` y formato local `es_CU`.
- Multi-negocio con alcance por cliente/negocio y soporte opcional de sub-negocio (`specific_business_id`).
- Trazabilidad documental de compras y movimientos internos para auditoria administrativa.

Contexto operativo del negocio (aclaracion funcional vigente):

- Existen negocios de distintos tipos/actividad: tiendas, restaurantes, bares, cafeterias, salon de belleza, casa de renta y servicios.
- El inventario debe responder a patrones distintos por actividad (comercial directa vs consumo productivo).

## 2.2) Decisiones cerradas (base actual y acuerdos tecnicos)

- El modulo actual ya gestiona catalogo basico de materias primas (`InventoryItem`) con CRUD simple.
- Existe base de persistencia para existencias por lote/entrada (`Inventory`) y extracciones (`InventoryExtraction`).
- El reporte de consumo de inventario derivado de ventas existe en `reports` y depende de servicios de ventas.
- Se mantiene arquitectura en capas: rutas del modulo, servicio de dominio y modelos dedicados.
- El ciclo contable de inventario se controlara en valor monetario con estos traspasos:
	- Compra/entrada: aumenta `inventario`.
	- Salida a exposicion: disminuye `inventario` y aumenta `mercancia_para_la_venta`.
	- Salida a WIP: disminuye `inventario` y aumenta `produccion_en_proceso`.
	- Cierre de elaboracion: disminuye `produccion_en_proceso` y aumenta `produccion_terminada`.
	- Venta de produccion terminada: disminuye `produccion_terminada` y aumenta `costo_de_venta`.
	- Produccion terminada marcada `va_a_exposicion`: no cambia de cuenta; solo cambia de ubicacion (`WIP/terminada` -> `exposicion`).
	- Merma de produccion terminada: disminuye `produccion_terminada` y aumenta `gastos_por_perdida`.
- Se manejaran dos salidas operativas de inventario:
	- mercancia a exposicion/venta directa,
	- mercancia a produccion en proceso (WIP).
- No todos los negocios usaran ambos flujos; la activacion de flujos sera configurable al crear/editar negocio.
- La mercancia en exposicion debe tener control propio de stock y reglas de reposicion por umbrales min/max.
- La reposicion en exposicion sera sugerida por el sistema y ejecutada manualmente por usuario.
- Los umbrales min/max se gestionaran por `item-ubicacion`.
- La produccion en proceso mantiene remanentes parciales hasta: consumo total, pase a produccion terminada o baja por merma.
- El pase de WIP a produccion terminada se ejecuta por consumo contra receta/venta.
- En restaurante/bar/cafeteria el flujo WIP estara activo por defecto, pero podra deshabilitarse.
- En otros tipos de negocio la configuracion de flujos (`exposicion`/`WIP`) sera editable y no fija.
- El sistema debe soportar entradas y salidas en unidades distintas (salida fraccionada respecto a unidad de entrada).
- La unidad base se define por item.
- Precision inicial confirmada: `g` con 2 decimales y `ml` con 2 decimales.
- Se permiten conversiones no exactas (mermas tecnicas de proceso).
- En conversiones no exactas se guardara siempre el motivo.
- Se requiere tarjeta de estiba (kardex por mercancia) con trazabilidad completa de entradas, salidas y saldo.
- La tarjeta de estiba se controlara por `item+lote`.
- Cuando una entrada requiera lote y no se capture manualmente, el sistema generara un lote automatico.
- La valorizacion de salidas seguira FEFO (primero lo que primero caduca); en empate de caducidad se aplica FIFO.
- Para productos sin caducidad aplica FIFO directo.
- Para productos sin caducidad no se usaran lotes.
- Las mermas base seran: `rotura`, `deterioro`, `caducidad` y `otros` (ampliable).
- Evidencia documental de merma sera opcional y podra ser texto y/o archivo/foto.
- No se permitira stock negativo; el sistema bloqueara salidas sin existencia suficiente.
- Se agregan alertas de bajo stock por tipo de producto.
- La alerta de bajo stock sera visual (no bloqueante).
- La alerta visual de bajo stock mostrara dos sugerencias: (a) reposicion hasta `max`, (b) reposicion calculada por consumo promedio.
- La sugerencia por consumo promedio usara ventas de los ultimos 7 dias.
- No se requieren ubicaciones fisicas adicionales en esta etapa.
- Se usara una sola ubicacion de exposicion en esta etapa.
- En exposicion pueden coexistir `mercancia_para_la_venta` (comprada a terceros) y `produccion_terminada` (elaborada), diferenciadas por su cuenta contable de origen.
- Clasificacion de mercancias requerida: producto generico (ej. granos), producto especifico (ej. arroz), producto surtido/variante (ej. arroz largo).
- Se creara una nueva tabla `insumos` como declaracion base del negocio, independiente de existencia fisica en inventario.
- Cada `insumo` pertenece a un negocio especifico.
- En `insumos` se gestionara `producto_generico` -> `producto_especifico` (relacional) y `producto_surtido` (singular/manual).
- Cardinalidad de catalogo global:
	- `producto_generico` (global) tiene muchos `producto_especifico`.
	- `producto_especifico` (global) pertenece a un solo `producto_generico`.
- Cardinalidad operativa por negocio:
	- `producto_surtido` es unico por negocio.
	- `producto_surtido` pertenece a un solo `producto_especifico`.
	- `producto_especifico` puede tener varios `producto_surtido`.
- En entradas de inventario se seleccionara `producto_surtido` desde `insumos`; los campos generico/especifico se derivan de esa relacion.
- `insumos` sera el vinculo entre inventario y ficha tecnica (receta) de producto.
- En traslado a exposicion, el stock de inventario general se descuenta al momento del traslado.
- Lo que sale del almacen no regresa a almacen en esta etapa.
- El sistema podra sugerir reposicion hasta `max`, pero la ejecucion sera manual.
- En WIP pueden existir subproductos intermedios que luego se consumen como materia prima de otras elaboraciones.
- Los subproductos en WIP se mantienen hasta: consumo posterior o merma.
- La ficha tecnica/receta definira raciones y consumos tecnicos de insumos.
- El campo `puede_ser_subproducto` se declarara en `Product` (no en la ficha tecnica compuesta).
- WIP tomara reglas desde ficha tecnica para descuentos por consumo y/o merma.
- Un subproducto WIP puede venderse directamente o consumirse como materia prima de otro producto.
- En transicion de venta directa de subproducto aplica `produccion_terminada -> costo_de_venta`.
- La bandera `va_a_exposicion` se declarara en `Product` y su valor por defecto sera `False`.
- Inventario tendra columna `documento` (usualmente numero de factura de compra) y ese valor se reflejara en tarjeta de estiba.
- La auditoria contable se concentra en adopcion/desadopcion de cuentas por negocio y asociaciones de subcuentas.
- Pendiente de cierre funcional: ninguno critico abierto en reglas nucleares; solo ajustes de implementacion tecnica.

## 3) Mapa de referencias internas (inventario util)

### 3.1 Modelos y persistencia

- `app/models/inventory.py` -> `InventoryItem`, `Inventory`, `InventoryExtraction`.
- `app/models/product.py` -> `Product`, `ProductDetail` (hoy receta usa `InventoryItem` directo).
- `app/models/account_classifier.py` -> `ACAccount`, `ACSubAccount`, `ACElement` (base actual reutilizable para nomenclador).
- `migrations/` -> pendientes nuevas migraciones para movimientos tipificados, ajustes y snapshot de stock.
- Pendiente de modelado nuevo: tabla `insumos` y catalogos de `producto_generico`/`producto_especifico`.
- Pendiente de modelado adicional: unicidad de `producto_surtido` por negocio.
- Pendiente de refactor en nomenclador: soporte de seleccion por negocio, subcuentas por negocio y auditoria de cambios.

### 3.2 Servicios de negocio

- `app/services/inventory_service.py` -> CRUD actual de items y resolucion de negocio.
- `app/services/income_report_service.py` -> calculo de consumo por ventas/recetas (base para reconciliacion de salidas).

### 3.3 Rutas y API

- `app/routes/inventory.py` -> gestion actual de items (`/item/list`, actualizacion).
- `app/routes/reports.py` -> `inventory_consumption` e `inventory_consumption_view`.

### 3.4 Formularios y templates

- `app/forms/inventory.py` -> `InventoryItemForm`.
- `app/templates/inventory/item_list.html` -> UI actual de alta/listado/edicion basica.
- `app/templates/report/inventory_consumption.html` -> vista de consumo por periodo.

## 4) Referencias externas de criterio (funcionales)

Resultado de busqueda web y contraste aplicado:

- Gestion de existencias y modelos de control (`ABC`, revision continua y periodica, stock de seguridad):
	- `https://es.wikipedia.org/wiki/Gestion_de_existencias`
- EOQ como referencia de optimizacion de lote (util para compras mas no suficiente por si solo en demanda variable):
	- `https://es.wikipedia.org/wiki/Cantidad_economica_de_pedido`
- Reglas de reabastecimiento min/max con activacion automatica/manual y logica JIT:
	- `https://www.odoo.com/documentation/17.0/es/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment/reordering_rules.html`
- Ajustes de inventario, conteos fisicos y trazabilidad de diferencias:
	- `https://www.odoo.com/documentation/17.0/es/applications/inventory_and_mrp/inventory/warehouses_storage/inventory_management/count_products.html`
- Flujo de desecho/merma con ubicacion virtual y trazabilidad de movimiento:
	- `https://www.odoo.com/documentation/17.0/es/applications/inventory_and_mrp/inventory/warehouses_storage/inventory_management/scrap_inventory.html`
- Modelo pull/kanban para reposicion por consumo real en exposicion o produccion:
	- `https://es.wikipedia.org/wiki/Kanban`
- Referencia normativa interna de cuentas (Cuba):
	- `docs/Nomenclador  de cuentas de la Actividad empresarial-MIPYMES-CNA-CPA-UBPC (1).pdf`
	- `docs/Uso y contenido de las cuentas de la Actividad empresarial-MIPYMES-CNA-CPA-UBPC (2).pdf`

Hallazgos de alineacion preliminar (Resolucion 494/2016):

- `183 Materias Primas y Materiales`: debita por adquisiciones/entradas, acredita por salidas a produccion/servicios, ventas y mermas.
- `188 Produccion Terminada`: debita por produccion terminada almacenada; acredita por costos de producciones vendidas, traslados internos y bajas (mermas/faltantes/roturas).
- `189 Mercancias para la Venta`: uso para mercancias compradas a terceros destinadas a venta directa.
- Cuentas de costo de venta identificadas en nomenclador: `1586 Costo de Ventas de la Produccion` y `1587 Costo de Ventas de Mercancias`.
- Implicacion funcional para este plan: `produccion_terminada` en exposicion conserva su naturaleza contable; solo cambia ubicacion operacional.
- Se implementara un `nomenclador_general_cuentas` (codigo + nombre) como maestro unico.
- El nomenclador se precargara inicialmente desde la Resolucion 494/2016.
- El nomenclador general sera de solo lectura (normativo): no se modifica codigo ni nombre de cuenta.
- Cada negocio seleccionara desde el nomenclador general las cuentas con las que va a operar.
- Las operaciones contables se ejecutaran solo sobre cuentas adoptadas por el negocio.
- Las subcuentas seran especificas por negocio.
- Se podra asociar cada subcuenta con su cuenta contable padre.

Pendiente para validacion funcional en la siguiente iteracion:

- [x] Definir politica de valorizacion de salida: FEFO y FIFO como desempate.
- [x] Definir politica operativa de mermas base y extensibilidad de causas.
- [ ] Definir estandar de conteo ciclico y frecuencia minima por tipo de insumo.
- [x] Definir que la activacion de flujos (`exposicion`, `WIP`) sea configurable al crear negocio.
- [x] Definir que los umbrales min/max se gestionan por `item-ubicacion`.
- [x] Definir que tarjeta de estiba se controla por `item+lote`.
- [x] Definir base de sugerencia por promedio: ventas de 7 dias.
- [x] Definir alcance de insumos: pertenece a negocio.
- [x] Definir cardinalidad de catalogo global (`generico` 1:N `especifico`) y surtido por negocio.
- [x] Definir unidad de captura en receta: `unidad_base_insumo` (Opcion A).
- [x] Definir que no existe transicion contable `produccion_terminada -> mercancia_para_la_venta`; en `va_a_exposicion=True` solo aplica cambio de ubicacion de `produccion_terminada`.
- [x] Definir arquitectura contable: nomenclador general + seleccion de cuentas por negocio + subcuentas por negocio.
- [x] Definir separacion contable de mermas: materias primas/materiales y produccion terminada.
- [x] Definir que ventas mixtas se descomponen en lineas `1586` y `1587` cuando corresponda.
- [x] Definir carga inicial del nomenclador: precargado desde Resolucion 494/2016 en modo solo lectura.
- [x] Definir relacion estructural cuenta-subcuenta para configuracion por negocio.
- [x] Definir que las operaciones y asociaciones contables ocurren sobre cuentas adoptadas por negocio.

## 5) Estado por fase y objetivos concisos

## Fase 1 - Saneamiento del catalogo maestro

Objetivo: normalizar catalogo de materias primas para evitar duplicados y errores de unidad.

### Entregables 1

- [x] CRUD basico de `InventoryItem` disponible.
- [ ] Validar unicidad por nombre normalizado (acentos/espacios/case).
- [ ] Estandarizar unidades de medida con catalogo controlado.
- [ ] Agregar estado activo/inactivo para descontinuados sin perder historial.
- [ ] Subfase 1.1: clasificar items por tipo de uso (`venta_directa`, `insumo_produccion`, `mixto`).
- [ ] Subfase 1.2: clasificar negocios por actividad operativa para reglas de inventario diferenciadas.
- [ ] Subfase 1.3: modelar jerarquia de mercancias (`generico` -> `especifico` -> `surtido/variante`).
- [ ] Subfase 1.4: separar modelo de catalogo (relacion generico-especifico) del modelo de entrada de inventario (campos directos generico/especifico/surtido por registro).
- [ ] Subfase 1.5: crear modelo `insumos` y enlazarlo con catalogos generico/especifico/surtido.
- [ ] Subfase 1.6: garantizar unicidad de `producto_surtido` por negocio.

## Fase 2 - Kardex minimo de movimientos

Objetivo: registrar entradas y salidas de inventario con tipologia operacional trazable.

### Entregables 2

- [ ] Definir tipos de movimiento: `purchase`, `consumption`, `transfer`, `adjustment`, `waste`.
- [ ] Definir destino de salida: `sales_floor` (exposicion) y `wip` (produccion_en_proceso).
- [ ] Persistir movimiento con referencia de origen (factura, venta, ajuste manual).
- [ ] Persistir movimientos con asiento contable asociado en valor monetario por transicion.
- [ ] Garantizar idempotencia en movimientos generados desde ventas.
- [ ] Exponer consulta de movimientos por item, negocio y rango de fechas.
- [ ] Subfase 2.1: generar tarjeta de estiba por `item+lote` con saldo acumulado.
- [ ] Subfase 2.2: generar lote automatico cuando aplique y no exista lote manual.

## Fase 3 - Control de exposicion y reposicion

Objetivo: controlar mercancia colocada para venta directa y automatizar reposicion por umbrales.

### Entregables 3

- [ ] Crear entidad de stock en exposicion por item y unica ubicacion de venta (etapa actual).
- [ ] Definir umbrales `min_exhibicion` y `max_exhibicion` por item-ubicacion.
- [ ] Implementar sugerencia de reposicion desde almacen a exposicion (manual/semiautomatica).
- [ ] Reposicion de exposicion: ejecucion manual con sugerencia automatica.
- [ ] Incluir doble sugerencia en alerta: `hasta_max` y `por_promedio_7_dias`.
- [ ] Alertar quiebre y sobrestock de exposicion.
- [ ] Alertar bajo stock en inventario general por tipo de producto.
- [ ] Subfase 3.1: compatibilidad con productos de tienda y negocios de venta directa.

## Fase 4 - Produccion en proceso (WIP) y produccion terminada

Objetivo: mantener trazabilidad de insumos parcialmente consumidos hasta su cierre.

### Entregables 4

- [ ] Crear entidad `inventory_wip_balance` por item/lote para salidas parciales.
- [ ] Registrar flujo `inventory -> wip -> finished_goods` con estados y cantidades.
- [ ] Permitir remanente en WIP y su consumo en multiples elaboraciones.
- [ ] Permitir que un producto terminado pase a subproducto en WIP para nuevas elaboraciones.
- [ ] Permitir baja de WIP por merma (`rotura`, `deterioro`, `caducidad`, `otros`).
- [ ] Fecha de vencimiento en WIP opcional por producto; si aplica, hereda o referencia caducidad de inventario.
- [ ] Permitir uso dual del subproducto WIP: venta directa o consumo en nuevas recetas.
- [ ] Restringir retorno de salidas a almacen (sin flujo de devolucion a almacen en esta etapa).
- [ ] Subfase 4.1: caso restaurante/bar/cafeteria (ej. consumo parcial de lata).
- [ ] Subfase 4.2: caso subproducto (ej. salsa base en WIP consumida despues por otras recetas).
- [ ] Subfase 4.3: contabilizacion monetaria de WIP -> terminada -> (venta | merma) y control de ubicacion para `terminada_en_exposicion`.

## Fase 5 - Existencias, conversion de unidades y valorizacion de stock

Objetivo: calcular stock y costo de forma consistente por negocio.

### Entregables 5

- [ ] Definir matriz de conversion de unidades por item (entrada vs salida).
- [ ] Soportar salida fraccionada de unidad de entrada sin perdida de precision.
- [ ] Definir regla de redondeo por tipo de unidad (inicial: `g` 2 decimales, `ml` 2 decimales).
- [ ] En conversiones no exactas, registrar motivo obligatorio.
- [ ] Implementar FEFO en salidas con FIFO como desempate en misma caducidad.
- [ ] Para no perecederos, aplicar FIFO sin lotes.
- [ ] Calcular stock disponible, stock comprometido y stock virtual.
- [ ] Registrar costo unitario vigente por item y costo de salida por movimiento.
- [ ] Validar no negativos con bloqueo de salida sin saldo.

## Fase 6 - Integracion robusta con ventas/recetas

Objetivo: sincronizar consumo real desde ventas sin descuadres de inventario.

### Entregables 6

- [ ] Mapear receta -> materias primas con equivalencias de unidad robustas.
- [ ] Leer desde ficha tecnica: raciones y consumos de insumos.
- [ ] Leer desde `Product`: bandera `puede_ser_subproducto` aplicable a todos los negocios.
- [ ] Leer desde `Product`: bandera `va_a_exposicion` (default `False`) para decidir ubicacion de produccion terminada.
- [ ] Descontar consumo automaticamente al confirmar venta.
- [ ] Revertir consumo en anulaciones/correcciones de venta.
- [ ] Detectar y reportar ventas con receta incompleta o materia prima inexistente.

## Fase 7 - Compras, entradas y lotes

Objetivo: formalizar entrada de inventario con soporte documental y trazabilidad temporal.

### Entregables 7

- [ ] Flujo de recepcion de compra con fecha, proveedor, documento y costo.
- [ ] Hacer obligatorio campo `documento` en entradas de inventario (base de tarjeta de estiba).
- [ ] Soporte de lotes (fecha, unidad, factor de conversion, costo).
- [ ] Registro de ajustes positivos/negativos con motivo obligatorio.
- [ ] Recalculo de costo medio tras cada entrada valida.

## Fase 8 - Mermas, caducidad y control preventivo

Objetivo: reducir perdida operativa con reglas preventivas.

### Entregables 8

- [ ] Registrar merma tipificada con causa y responsable.
- [ ] Alertas por stock minimo y proximidad de vencimiento.
- [ ] Bloqueo o alerta configurable ante consumo que rompa stock minimo.
- [ ] Evidencia documental opcional en registro de merma.
- [ ] Soportar evidencia de merma en texto y/o archivo/foto.
- [ ] Reporte de merma por item, causa y periodo.

## Fase 9 - Conteo fisico y conciliacion

Objetivo: cerrar brecha entre stock teorico y stock fisico.

### Entregables 9

- [ ] Flujo de conteo ciclico por ubicacion/item.
- [ ] Conciliacion con propuesta automatica de ajuste.
- [ ] Registro de evidencia del conteo (usuario, fecha, observacion).
- [ ] Ajustes sin flujo de aprobacion por umbral en esta etapa (umbral se modifica manualmente cuando aplique).

## Fase 10 - Reportes operativos y financieros

Objetivo: convertir inventario en herramienta de decision diaria.

### Entregables 10

- [ ] Kardex valorizado por item y periodo.
- [ ] Reporte de rotacion y dias de cobertura.
- [ ] Reporte de quiebres de stock y riesgo de quiebre.
- [ ] Reporte de costo de consumo asociado a ventas.
- [ ] Tarjeta de estiba por item/lote/ubicacion con saldo corrida.
- [ ] Tarjeta de estiba mostrando columna `documento` desde movimiento/entrada.
- [ ] Sin exportacion en etapa actual (consulta en pantalla/API).

## Fase 11 - UX/UI y modularidad tecnica

Objetivo: modernizar experiencia de inventario y reducir friccion operativa.

### Entregables 11

- [ ] Auditar vistas actuales de inventario y consumo.
- [ ] Extraer partials reutilizables para formularios, tabla y paneles.
- [ ] Incorporar HTMX para altas/ediciones/ajustes sin recargas completas.
- [ ] Mantener fallback clasico y consistencia visual con el sistema actual.

## Fase 12 - Reproceso historico y hardening

Objetivo: asegurar confiabilidad antes del cierre de implementacion.

### Entregables 12

- [ ] Script de reconstruccion historica de stock por negocio.
- [ ] Validacion de consistencia entre movimientos, existencias y reportes.
- [ ] Pruebas smoke end-to-end en entorno `webdev`.
- [ ] Checklist de regresion cruzada con ingresos/reportes.

## Fase 13 - Integracion contable de inventario

Objetivo: reflejar cada transicion de inventario/WIP/terminada en cuentas monetarias de control.

### Entregables 13

- [ ] Motor de asientos para transiciones definidas del ciclo contable de inventario.
- [ ] Trazabilidad por movimiento: documento, monto, cuenta origen, cuenta destino.
- [ ] Reglas de valorizacion alineadas a FEFO/FIFO para importes de salida.
- [ ] Reporte de conciliacion: saldos de cuentas vs saldos operativos de stock.
- [ ] Reusar y extender `ACAccount` como `nomenclador_general_cuentas` (sin duplicar modelo paralelo).
- [ ] Crear carga inicial (seed/migracion) del nomenclador desde Resolucion 494/2016.
- [ ] Bloquear edicion de codigo y nombre en `ACAccount` cuando pertenezca al nomenclador general normativo.
- [ ] Configurar seleccion de cuentas por negocio desde el nomenclador general.
- [ ] Restringir asientos y operaciones a cuentas previamente adoptadas por negocio.
- [ ] Reusar y extender `ACSubAccount` para subcuentas por negocio.
- [ ] Modelar relacion obligatoria subcuenta -> cuenta padre.
- [ ] Implementar auditoria de adopcion/desadopcion y asociaciones cuenta-subcuenta por negocio.
- [ ] Separar asiento de merma de materias primas/materiales y merma de produccion terminada.
- [ ] En ventas mixtas, descomponer costo en lineas `1586` (produccion) y `1587` (mercancias).

### Criterios de aceptacion 13

- [ ] DB: el nomenclador general cargado desde Resolucion 494/2016 queda marcado como normativo e inmutable (`codigo`, `nombre`).
- [ ] DB: existe estructura de adopcion de cuenta por negocio (cuenta general -> negocio) sin duplicar el catalogo normativo.
- [ ] DB: toda subcuenta de negocio referencia obligatoriamente una cuenta adoptada del propio negocio.
- [ ] API: cualquier intento de editar `codigo` o `nombre` de una cuenta normativa retorna error de validacion controlado.
- [ ] API: no se permite registrar asiento ni configuracion operativa sobre cuenta no adoptada por el negocio.
- [ ] API: al desadoptar una cuenta, se bloquea la accion si existen subcuentas activas o movimientos asociados sin cerrar.
- [ ] UI: en mantenimiento de nomenclador general, `codigo` y `nombre` se muestran solo lectura.
- [ ] UI: la gestion contable del negocio expone flujo explicito de `adoptar/desadoptar` cuentas normativas.
- [ ] Auditoria: se registra adopcion/desadopcion y alta/baja/edicion de subcuentas por negocio (usuario, fecha, antes, despues).
- [ ] Pruebas: casos automatizados cubren bloqueo de edicion normativa, restriccion de uso sin adopcion y trazabilidad de auditoria.

## 6) Tablero de ejecucion activo

### Bloque inmediato (siguiente sprint tecnico)

- [ ] F1.1 Definir taxonomia de negocio y flujos activos por negocio (exposicion/WIP).
- [ ] F1.2 Definir jerarquia de mercancias (`generico`/`especifico`/`surtido`) y catalogo de unidades.
- [ ] F1.3 Diseñar tabla `insumos` como base de declaracion y vinculo con receta/inventario.
- [ ] F1.4 Modelar restricciones de unicidad de surtido por negocio y relaciones de catalogo.
- [ ] F2.1 Diseñar modelo de movimiento de inventario con destino (`sales_floor`/`wip`).
- [ ] F2.2 Confirmar lote automatico y tarjeta de estiba por `item+lote`.
- [ ] F3.1 Modelar stock de exposicion y reglas min/max de reposicion.
- [ ] F3.2 Aplicar descuento inmediato del almacen al trasladar a exposicion.
- [ ] F3.3 Implementar alerta con doble sugerencia (`hasta_max`, `promedio_7_dias`).
- [ ] F4.1 Modelar flujo WIP con consumo parcial y merma de remanentes.
- [ ] F4.2 Modelar subproductos en WIP para consumo en elaboraciones posteriores.
- [ ] F4.3 Permitir subproducto WIP para venta directa y consumo en recetas.
- [ ] F4.4 Implementar `va_a_exposicion` para produccion terminada sin cambio de cuenta contable.
- [ ] F13.1 Diseñar asientos contables por transicion monetaria de inventario.
- [ ] F13.2 Diseñar nomenclador general y selector de cuentas por negocio.
- [ ] F13.3 Diseñar subcuentas por negocio con asociacion obligatoria a cuenta padre y separacion de mermas por tipo.
- [ ] F13.4 Diseñar desglose contable de ventas mixtas (`1586`/`1587`).
- [ ] F13.5 Diseñar y aplicar auditoria de adopciones y asociaciones contables por negocio.

### Paquete de arranque (ejecucion inmediata)

- [x] TKT-INV-001 (`F1.3`): crear migracion de `supplies` con FK a negocio y referencia a surtido.
- [x] TKT-INV-002 (`F1.3`): crear modelo/servicio `Supply` y validaciones de pertenencia por negocio.
- [x] TKT-INV-003 (`F1.3`): exponer endpoints CRUD de `supplies` con filtros por negocio y pruebas basicas.
- [x] TKT-INV-004 (`F2.1`): crear tabla de movimientos tipificados con destino (`sales_floor`/`wip`) y referencia de origen.
- [x] TKT-INV-005 (`F2.1`): implementar servicio de movimientos con regla de no-negativos e idempotencia base.
- [x] TKT-INV-006 (`F2.1`): agregar consulta de movimientos por item/negocio/rango y prueba de regresion.
- [x] TKT-INV-007 (`F4.1`): crear tabla `inventory_wip_balance` y estados minimos de ciclo (`abierto`, `cerrado`, `merma`).
- [x] TKT-INV-008 (`F4.1`): implementar transiciones `inventory -> wip -> finished_goods` con validaciones de saldo.
- [x] TKT-INV-009 (`F4.1`): cubrir caso de consumo parcial y merma de remanente con pruebas de servicio.
- [x] TKT-INV-010 (`F13.2`): modelar adopcion de cuentas por negocio reutilizando `ACAccount` (sin duplicar nomenclador).
- [x] TKT-INV-011 (`F13.2`): bloquear edicion de `codigo`/`nombre` en cuentas normativas y validar en API.
- [x] TKT-INV-012 (`F13.2`): exponer flujo `adoptar/desadoptar` cuenta por negocio con auditoria minima.
- [x] TKT-INV-013 (`F13.2`): restringir operaciones contables a cuentas adoptadas y cubrir casos de rechazo.

### Definition of Done (arranque)

- [ ] Cada ticket incluye migracion (si aplica), servicio, ruta/API y prueba minima automatizada.
- [ ] Ningun ticket rompe reportes actuales de consumo (`inventory_consumption`).
- [ ] Se ejecuta smoke en `webdev` con alta de insumo, movimiento, paso por WIP y adopcion de cuenta.
- [ ] Toda regla de negocio nueva queda trazada en bitacora tecnica del plan.

### Bloque siguiente

- [ ] F5.1 Implementar conversion de unidades y salida fraccionada segura.
- [ ] F6.1 Integrar receta/ventas con consumos idempotentes y reversibles.
- [ ] F7.1 Crear flujo de entrada de compras con evidencia documental y lotes.
- [ ] F8.1 Implementar mermas y politicas por causa/actividad.
- [ ] F9.1 Conteo ciclico y conciliacion con trazabilidad de responsable.
- [ ] F10.1 Publicar reportes de tarjeta de estiba, reposicion y WIP.

## 7) Bitacora de avance

- 2026-03-05: Se crea plan maestro inicial de inventario alineado al formato y criterios de `plan_fases_income.md`.
- 2026-03-05: Se documenta estado real detectado: CRUD basico de items, modelos de inventario/extracciones y reportes de consumo existentes.
- 2026-03-05: Se integra contexto operativo solicitado (tipos de negocio, salidas a exposicion y WIP, unidades fraccionadas y tarjeta de estiba).
- 2026-03-05: Se contrasta plan con referencias de modelos de inventario (ABC/EOQ/min-max/JIT/ajustes/mermas) y se agregan fases/subfases nuevas.
- 2026-03-05: Se incorporan respuestas del cuestionario: flujos configurables por negocio, reposicion sugerida/manual, FEFO+FIFO, bloqueo de negativos, precision por unidad, mermas base y evidencia opcional.
- 2026-03-05: Se agrega requisito de clasificacion de mercancias en niveles `generico`, `especifico` y `surtido/variante`.
- 2026-03-05: Se ajusta plan con nuevas definiciones: umbrales por `item-ubicacion`, WIP por defecto en restaurante/bar/cafeteria (deshabilitable), FIFO para no perecederos y precision `g`/`ml` a 2 decimales.
- 2026-03-06: Se confirman reglas finales de trazabilidad: tarjeta por `item+lote`, lote automatico cuando aplique, no uso de lotes para no perecederos y una sola ubicacion de exposicion.
- 2026-03-06: Se incorpora flujo de subproductos en WIP (producto intermedio que luego actua como materia prima de otras elaboraciones).
- 2026-03-06: Se define estructura de datos de entrada con campos directos `producto_generico`, `producto_especifico` y `producto_surtido`, separada del catalogo relacional.
- 2026-03-06: Se define alerta con doble sugerencia de reposicion (`hasta max` y `promedio 7 dias`) y se integra uso de ficha tecnica (raciones/consumos) + bandera de subproducto en `Product`.
- 2026-03-06: Se integra ciclo contable monetario de inventario/WIP/terminada y se planifica nueva tabla `insumos` como vinculo entre receta e inventario.
- 2026-03-06: Se cierran cardinalidades: insumo por negocio, catalogo global generico/especifico y surtido unico por negocio con trazabilidad por documento en tarjeta de estiba.
- 2026-03-09: Se cierra unidad de receta en `unidad_base_insumo` (Opcion A) y se corrige exposicion contable: `produccion_terminada` no pasa a `mercancia_para_la_venta`, solo cambia de ubicacion cuando `va_a_exposicion=True` (default `False`).
- 2026-03-09: Se define arquitectura contable con nomenclador general, seleccion de cuentas por negocio, subcuentas especificas por negocio, separacion de mermas por tipo y desglose de ventas mixtas en `1586`/`1587`.
- 2026-03-09: Se redefine el nomenclador general como base normativa inmutable (solo lectura), precargada desde Resolucion 494/2016.
- 2026-03-09: Se valida reutilizar `ACAccount/ACSubAccount/ACElement` y se fija que cada negocio adopta cuentas del nomenclador general para operar; se audita adopcion/desadopcion y asociaciones cuenta-subcuenta.
- 2026-03-09: Se agregan criterios de aceptacion tecnicos (DB/API/UI/Auditoria/Pruebas) para garantizar que el nomenclador general sea inmutable y que la operacion ocurra solo sobre cuentas adoptadas por negocio.
- 2026-03-09: Se define paquete de arranque con tickets tecnicos ejecutables (`TKT-INV-001` a `TKT-INV-013`) para iniciar implementacion por capas en `F1.3`, `F2.1`, `F4.1` y `F13.2`.
- 2026-03-09: Se implementan `Supply` y `InventoryMovement` en modelos/servicios/rutas (`/supply/list`, `/supply/create`, `/movement/list`, `/movement/create`) con convencion de codigo en ingles y mensajes/API en espanol.
- 2026-03-09: Se agrega migracion de compatibilidad para renombrar `insumo` -> `supply` en bases existentes y mantener continuidad de despliegues.
- 2026-03-09: Se completan endpoints `Supply` para `update/delete` y se agrega filtro por rango de fechas en `/movement/list` (`start_date`, `end_date`) con validacion de formato.
- 2026-03-09: Se implementa `InventoryWipBalance` (modelo + migracion), junto a endpoints/servicio WIP (`/wip/list`, `/wip/create`, `/wip/<id>/consume`, `/wip/<id>/finish`, `/wip/<id>/waste`) para abrir `F4.1` con consumo parcial y merma operativa.
- 2026-03-09: Se implementa adopcion de cuentas por negocio sobre nomenclador general (`BusinessAccountAdoption`) con migracion y API (`/account-adoption/list`, `/account-adoption/adopt`, `/account-adoption/unadopt`).
- 2026-03-09: Se blinda inmutabilidad del nomenclador general con guard de modelo (`before_update` en `ACAccount`) y rechazo API explicito de edicion (`/account-catalog/update`), manteniendo consulta de catalogo en solo lectura (`/account-catalog/list`).
- 2026-03-09: Se implementa auditoria de adopcion/desadopcion con `BusinessAccountAdoptionAudit` y endpoint de consulta (`/account-adoption/audit-list`), registrando actor, origen y cambio de estado.
- 2026-03-09: Se agrega `account_code` en `InventoryMovement` para operacion contable controlada y se valida adopcion activa por negocio; se bloquea desadopcion cuando la cuenta tiene movimientos asociados.
- 2026-03-09: Se hace obligatorio `account_code` adoptado para registrar movimientos (`/movement/create`) y para transferencias a WIP (`/wip/create`), reforzando rechazo de operaciones contables fuera de cuentas adoptadas.
- 2026-03-09: Se completa el cierre contable `wip -> finished_goods` en `/wip/<id>/finish`, registrando movimiento `wip_close` con `account_code` adoptado obligatorio y referencia al balance WIP cerrado.
- 2026-03-09: Se agregan pruebas de servicio en `tests/services/test_inventory_service.py` y pasan en `webdev` (`python -m unittest discover -s tests -p 'test_*.py'`): consumo parcial WIP, merma WIP, cierre WIP con `wip_close` y filtro de movimientos por item/rango.
- 2026-03-09: Se agregan pruebas de rutas para CRUD de `supplies` en `tests/routes/test_inventory_supply_routes.py` (list/create/update/delete) y pasan en `webdev` junto a pruebas de servicio (`8 tests OK`).
