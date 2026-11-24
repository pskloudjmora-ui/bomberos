# Plan de trabajo — Mejoras del sistema de reportes bomberiles (v2)

**Fecha:** 24/11/2026  
**Base analizada:** `bomberos.db` local + código en el commit `a11807a`  
**Alcance:** mejoras transversales, MATPEL, APH, incendios, siniestros viales, rescates, búsqueda y rescate, fauna y eliminación de Baldeo.

---

## 1. Resumen ejecutivo

El sistema ya tiene una base sólida: herencia polimórfica por `tipo_reporte`, formulario único en `crear.html`, PDF centralizado en `pdf_service.py` y migraciones mínimas por `COLUMNAS_NUEVAS`. La mayoría de los campos solicitados **ya existen en los modelos** (temperatura, Glasgow, firmas APH, horas de salida por unidad, datos de cadáver, etc.); el trabajo principal es de **formulario, validación, detalle y PDF**, más una capa nueva para **unidades y vehículos involucrados reutilizables**.

La base local tiene **3 reportes** (2 GLP y 1 químico), **2 filas de unidades actuantes** y **1 vehículo** en catálogo. El riesgo de migración es bajo, pero hay que conservar los reportes históricos y sus PDF.

**Decisión clave:** crear dos componentes compartidos antes de tocar los formatos:

1. **Unidades actuantes** (cabecera + sección 3) con tipo de unidad, unidad libre y hora de salida propia.
2. **Vehículos involucrados** (tabla nueva + macro Jinja) reutilizable en MATPEL, siniestros e incendios, con conductor/propietario.

Sin esa base, cada formato repetiría la misma lógica y se multiplicarían los errores.

**Duración estimada:** 15-19 jornadas de desarrollo + 2 de QA. Las fases 2-7 pueden paralelizarse parcialmente una vez terminada la fase 1.

---

## 2. Estado actual verificado

### 2.1 Base de datos

- 25 tablas; `db.create_all()` no altera tablas existentes.
- `COLUMNAS_NUEVAS` en `app/__init__.py` solo agrega columnas; **no cambia nulabilidad ni renombra columnas**.
- Reportes existentes:

| Tipo | Tabla | Filas |
|---|---|---:|
| Control de GLP | `reportes_matpel_glp` | 2 |
| Derrame químico | `reportes_matpel_quimico` | 1 |
| Resto de tipos | — | 0 |

- `reporte_vehiculos_actuantes`: 2 filas. Ya tiene `hora_salida`, pero `vehiculo_id` es **NOT NULL** y no existe tipo de unidad ni unidad libre.
- `vehiculos`: 1 fila (catálogo insuficiente para “unidad adicional”).
- `postgres_schema.sql` es una foto generada del esquema; quedará desactualizado si no se regenera.

### 2.2 Código y formularios

| Área | Estado actual |
|---|---|
| Cabecera | Horas globales (aviso, salida, llegada, regreso), itinerario y cuadrante. No hay selección de unidades en la cabecera. |
| Sección 3 | Tabla dinámica de vehículos actuantes con conductor, hora de salida y km. Tiene botón “Añadir Unidad”. |
| Incendios | Bloque de despacho propio con `salida_primera_maquina`, `salida_segunda_maquina`, `salida_ambulancia`, `salida_unidad_adicional` y nombre. Duplica el concepto de unidad. |
| Vehículos afectados | JSON (`vehiculos_afectados_json`) y partial `_vehiculos_afectados.html` usado solo por incendio de vehículo/apoyo. |
| MATPEL | Vehículo único en columnas (`vehiculo_marca`, `vehiculo_modelo`, etc.). No hay múltiples vehículos ni conductor/propietario en combustible/químico. |
| APH | Modelos con temperatura, Glasgow, `medico_firma` y `rechazo_firma`; **el formulario no muestra esos campos**. El Traslado Rutinario (`pre_hospitalario`) no tiene esas columnas. |
| Incendios por subtipo | Partiales `_incendio_params_*.html`; eléctrico conserva humo/total, desechos no tiene fuego, vegetación/árbol conservan humo/total. |
| Siniestros | 4 tipos (`rescate_colision_*`, `rescate_volcamiento_*`), vehículos en textarea, sin selector de tipo de siniestro, sin sección de lesionados. El backend ya acepta `veh_inv_*[]`, pero el formulario no los envía. |
| Rescates | Ascensor/inmueble/tapiada/golpeada muestran “Despliegue Operacional” completo; caída/cadáver omiten secciones 3–5. No hay personas rescatadas, motivo ni hora de ambulancia. |
| Fauna | Selects con opción “Otro” sin `onchange` ni input de texto. |
| Baldeo | Presente en menús, rutas, KPIs, dashboard, detalle y PDF. |
| Numeración | En el formulario, caída/cadáver ocultan 3–5 y saltan de 2 a 6. En PDF, la sección de observaciones se rotula como 3 y las firmas como 7. En detalle se ocultan 3–5 y la numeración fija queda inconsistente. |

### 2.3 Puntos que ya funcionan y no hay que rehacer

- Autogeneración de `nro_control` por prefijo y año.
- Parseo de horas 24 h con segundos.
- Resolución genérica de “Otro” → `{campo}_otro` en `crear_reporte`.
- Guardado de personas afectadas para cualquier `aph_*` o `rescate_*`.
- Serialización de PDF y DTO.
- Migración idempotente de columnas al arrancar.

---

## 3. Decisiones de arquitectura propuestas

### D1. Una sola tabla de unidades actuantes

**Recomendación:** extender `reporte_vehiculos_actuantes` (concepto “unidades actuantes”) en lugar de crear otra tabla:

- `tipo_unidad`: `primera_maquina`, `segunda_maquina`, `ambulancia`, `adicional`.
- `nombre_unidad_libre`: para moto institucional u otra unidad que no esté en el catálogo.
- `conductor_cedula`.
- `hora_regreso` (opcional).
- `orden`.
- `vehiculo_id` pasa a **nullable**.

La cabecera (sección 1) tendrá un bloque compacto de despacho con checkboxes para Primera, Segunda, Ambulancia y “Otra unidad”; cada selección **agrega una fila** a la tabla de la sección 3, que sigue siendo la fuente única de verdad. Así no se duplican datos y cada unidad conserva su hora de salida.

**Compatibilidad:** las columnas `salida_*` de `reportes_incendio` se conservan para reportes históricos y como respaldo del PDF, pero dejan de pedirse en formularios nuevos.

### D2. Tabla nueva de vehículos involucrados + macro reutilizable

**Recomendación:** crear `reporte_vehiculos_involucrados` y un partial/macro `_vehiculos_involucrados.html` con opciones:

- `mostrar_carga` (solo incendio de vehículo).
- `mostrar_valor` / `mostrar_condicion`.
- `prefijo` de campos (`vi_`).

Vehículos de MATPEL, siniestros e incendios comparten estructura:

`marca`, `modelo`, `color`, `placa`, `tipo`, `uso`, `serial_carroceria`, `serial_motor`, `anio`, `condicion`, `valor`, `perdidas`, `aseguradora`, `conductor_nombre`, `conductor_cedula`, `conductor_telefono`, `conductor_edad`, `propietario_nombre`, `propietario_cedula`, `propietario_telefono`, `propietario_edad`.

Los campos de carga (`valor_carga`, `perdida_carga`, `aseguradora_carga`) se incluyen en la tabla pero se ocultan en los formatos que no los usan. El JSON existente se conserva como **fallback de lectura** para reportes históricos; no se migra masivamente.

### D3. Personas rescatadas / lesionados: reutilizar `reporte_personas_afectadas`

La tabla ya tiene nombre, cédula, edad, sexo, lesión y residencia. Se usa para:

- lesionados de siniestros viales,
- personas rescatadas de ascensor, inmueble, tapiada, golpeada y búsqueda,
- pacientes APH (como ya se hace).

No se necesita tabla nueva. Se creará un partial `_personas_afectadas.html` para el formulario y se reutilizará el macro existente `_macros_paciente.html` en detalle.

### D4. Estructura / almacenamiento no vehicular: columnas en las tablas MATPEL

Para derrame de combustible y derrame químico se agregan columnas de estructura/responsable/empresa. No se crea tabla aparte porque el requerimiento describe **un** origen por reporte, no una lista.

### D5. “Otros” centralizado

Mantener `manejarOtros(select, inputId)` y aplicarlo a todos los selects con opción “Otro”. El backend ya resuelve `{campo}_otro`; solo hay que asegurar que el input exista y se muestre.

### D6. Baldeo: retirar de la operación, conservar historia

**Recomendación:** eliminar Baldeo de menús, creación, dashboard y KPIs, pero **no borrar la tabla ni los modelos**. Los reportes históricos deben seguir abriéndose en detalle/PDF. Si se confirma que no hay datos que conservar, se puede borrar la tabla en una migración posterior.

### D7. Siniestros viales: dos tipos canónicos

**Recomendación:**

- `siniestro_vial_con_lesionado` → `ReporteRescateColision`, `subtipo_rescate='siniestro_vial_con_lesionado'`.
- `siniestro_vial_sin_lesionado` → `ReporteRescateColision`, `subtipo_rescate='siniestro_vial_sin_lesionado'`.

El selector `tipo_siniestro` (colisión / volcamiento / choque / otro) queda dentro de parámetros técnicos. Los 4 tipos antiguos se mantienen como **legacy** en `REPORT_MODEL_MAP` para no romper enlaces históricos, pero se ocultan de los menús. Hay que ajustar `Reporte.tipo_especifico` para que devuelva `siniestro_vial_*` cuando el subtipo empiece con ese prefijo.

### D8. Firmas APH

El modelo ya tiene `medico_firma` y `rechazo_firma` como booleanos. **Supuesto inicial:** son casillas de constancia (“firma registrada”), no imágenes. Si el usuario requiere firma manuscrita digitalizada, habría que agregar almacenamiento de archivo/imagen y incrustarla en el PDF (ver pregunta 4).

---

## 4. Fases de trabajo

### Fase 0 — Confirmación de decisiones y línea base (0,5 j)

**Objetivo:** cerrar las preguntas de la sección 8 y congelar una copia de la BD para pruebas.

Tareas:

1. Revisar y responder las preguntas abiertas.
2. Copiar `bomberos.db` a `bomberos_pre_mejoras.db` (respaldo local).
3. Ejecutar la app y generar PDF de los 3 reportes existentes para comparar después.
4. Confirmar si se actualiza también `postgres_schema.sql`.

**Salida:** decisiones firmadas y respaldo de datos.

---

### Fase 1 — Infraestructura compartida (3 j)

**Objetivo:** unidades, vehículos involucrados, personas y “Otros” reutilizables.

#### 1.1 Unidades actuantes

**Modelo** (`app/models.py`):

```python
class ReporteVehiculoActuante(db.Model):
    ...
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculos.id'), nullable=True)
    tipo_unidad = db.Column(db.String(30), nullable=True)
    nombre_unidad_libre = db.Column(db.String(150), nullable=True)
    conductor_cedula = db.Column(db.String(20), nullable=True)
    hora_regreso = db.Column(db.Time, nullable=True)
    orden = db.Column(db.Integer, nullable=True)
```

**Migración** (`app/__init__.py`):

- Agregar columnas a `COLUMNAS_NUEVAS`.
- Para SQLite, `vehiculo_id` sigue siendo NOT NULL en la tabla existente. Implementar `_migrar_unidades_actuantes()` idempotente que:
  1. Lee `PRAGMA table_info(reporte_vehiculos_actuantes)`.
  2. Si `vehiculo_id.notnull == 1`, renombra la tabla, crea la nueva con `vehiculo_id` nullable, copia los datos y elimina la antigua.
  3. En PostgreSQL, `ALTER TABLE ... ALTER COLUMN vehiculo_id DROP NOT NULL`.

**Formulario** (`crear.html`):

- Sección 1: bloque “Unidades despachadas” con checkboxes Primera / Segunda / Ambulancia / Otra + texto + hora.
- Sección 3: columnas “Tipo”, “Unidad” (select con opción “Otra unidad” + input libre), conductor, cédula, hora salida, km salida, km regreso.
- JS: `agregarUnidadCabecera(tipo)` crea la fila en `#contenedor-vehiculos` con tipo y hora precargados; no duplica si ya existe.

**Backend** (`app/routes/reportes.py`):

- Parsear `tipos_unidad[]`, `unidades_libres[]`, `conductores[]`, `conductores_cedula[]`, `horas_salida_vehiculo[]`, km.
- Guardar `vehiculo_id` o `nombre_unidad_libre` según corresponda.
- Validar: al menos una unidad, conductor obligatorio, hora válida.

**Detalle/PDF:**

- Mostrar `va.vehiculo.unidad` o `va.nombre_unidad_libre`.
- Mostrar etiqueta legible del `tipo_unidad`.
- Mantener fallback a `salida_*` de incendios si no hay filas de unidades.

**Criterio de aceptación:** un reporte con 4 unidades (una libre, p. ej. “Moto institucional”) y horas distintas se guarda, se ve en detalle y en PDF.

#### 1.2 Vehículos involucrados

**Modelo nuevo** `ReporteVehiculoInvolucrado` (`reporte_vehiculos_involucrados`):

```text
id, reporte_id (FK CASCADE), orden,
marca, modelo, color, placa, tipo, uso,
serial_carroceria, serial_motor, anio,
condicion, valor, perdidas, aseguradora,
conductor_nombre, conductor_cedula, conductor_telefono, conductor_edad,
propietario_nombre, propietario_cedula, propietario_telefono, propietario_edad,
valor_carga, perdida_carga, aseguradora_carga
```

Relación `Reporte.vehiculos_involucrados` con `cascade='all, delete-orphan'`.

**Partial** `_vehiculos_involucrados.html`:

- Macro `campo_texto`, `campo_numero`, `campo_select`.
- Contenedor dinámico con botón “Agregar unidad”.
- Parámetros: `mostrar_carga`, `mostrar_valor`, `prefijo`.
- JS `agregarVehiculoInvolucrado(contenedorId, prefijo)` y `eliminarVehiculoInvolucrado(btn)`.

**Backend:** helper `_guardar_vehiculos_involucrados(reporte, form, prefijo='vi_')` que lee listas `vi_marca[]`, etc., y crea filas. Se llama desde MATPEL y siniestros.

**Lectura:** helper `vehiculos_involucrados_de(reporte)` que devuelve filas nuevas; si no hay, parsea `vehiculos_afectados_json` o `vehiculos_involucrados_json` para históricos.

**Criterio de aceptación:** dos vehículos con conductor y propietario se guardan y se muestran en detalle/PDF; un reporte histórico con JSON sigue mostrando sus datos.

#### 1.3 Personas afectadas / rescatadas

- Partial `_personas_afectadas.html` con filas dinámicas (`pa_nombre[]`, `pa_cedula[]`, `pa_edad[]`, `pa_sexo[]`, `pa_lesion[]`, `pa_residencia[]`).
- Título configurable: “Lesionados” o “Personas Rescatadas”.
- Incluir en siniestros y en todos los rescates que lo requieran.
- Backend: ampliar la condición de guardado a `tipo_reporte.startswith('siniestro_')` además de `aph_*`/`rescate_*`.

#### 1.4 “Otros” en selects

- Auditar todos los `<option value="Otro">` de `crear.html`.
- Añadir `onchange="manejarOtros(this, '<campo>_otro')"` e input oculto.
- Casos obligatorios: `servicio_insectos.tipo_insecto`, `servicio_animal.tipo_animal`, `riesgo_producto`, `tipo_siniestro`.
- Verificar que el backend resuelva el valor de texto en `crear_reporte`.

#### 1.5 Migración y paridad

- Agregar columnas nuevas a `COLUMNAS_NUEVAS`.
- `db.create_all()` crea las tablas nuevas.
- Regenerar `postgres_schema.sql` al final de la fase.
- Probar en copia de `bomberos.db` y en base vacía; ejecutar dos veces para verificar idempotencia.

**Archivos de la fase:** `app/models.py`, `app/__init__.py`, `app/routes/reportes.py`, `app/services/pdf_service.py`, `app/templates/reportes/crear.html`, `detalle.html`, `reporte_pdf.html`, `_vehiculos_involucrados.html` (nuevo), `_personas_afectadas.html` (nuevo), `postgres_schema.sql`.

---

### Fase 2 — MATPEL: combustible, GLP, químico y gas natural (2 j)

**Depende de:** fase 1.

#### 2.1 Derrame de combustible (`matpel_combustible`)

Formulario (`crear.html`, sección 2.2):

- Eliminar el checkbox “El vehículo ocasionó el derrame” (`vehiculo_afecto`).
- Agregar selector `origen_derrame`: “Vehículo” / “Estructura o almacenamiento”.
- Si es vehículo: incluir `_vehiculos_involucrados.html` (múltiples, conductor/propietario, sin carga).
- Si es estructura: mostrar `tipo_estructura`, `responsable_nombre`, `responsable_cedula`, `responsable_telefono`, `empresa_nombre`, `empresa_rif`.
- Agregar `riesgo_producto` (select con “Otro” + texto) junto a `un_numero`.
- Mantener `tipo_combustible` y `tipo_almacenamiento`.

Modelo/BD:

- `origen_derrame VARCHAR(20)`, `riesgo_producto VARCHAR(150)`.
- `tipo_estructura VARCHAR(100)`, `responsable_nombre VARCHAR(150)`, `responsable_cedula VARCHAR(20)`, `responsable_telefono VARCHAR(30)`, `empresa_nombre VARCHAR(150)`, `empresa_rif VARCHAR(30)`.
- `vehiculos_involucrados_json` se conserva como legacy; los nuevos vehículos van a `reporte_vehiculos_involucrados`.

Detalle/PDF:

- Bloque “Origen del derrame”.
- Tabla de vehículos involucrados (si aplica).
- Bloque de estructura/responsable (si aplica).
- “Riesgo del producto”.

#### 2.2 Control de GLP (`matpel_glp`)

- Reemplazar los campos únicos `vehiculo_marca/modelo/placa/color/vehiculo_afecto` por `_vehiculos_involucrados.html` con múltiples unidades y conductor/propietario.
- Conservar estructura, propietario, empresa, certificado y checklist.
- Reutilizar los campos existentes `propietario_nombre`, `propietario_rif_ci` y `empresa_distribuidora` para el responsable/empresa; no hace falta una columna nueva.
- Detalle/PDF: tabla de vehículos.

#### 2.3 Derrame químico (`matpel_quimico`)

- Renombrar la etiqueta “Tipo de combustible” a **“Nombre de la sustancia”** (la columna `nombre_sustancia` ya existe; no renombrar la columna).
- Agregar `origen_derrame` (Vehículo / Estructura) con los mismos bloques condicionales que combustible.
- Para vehículo, usar la misma estructura de Información del vehículo (marca, modelo, color, placa, tipo, uso, serial carrocería, serial motor, año).
- Mantener `riesgos_especificos` como “Riesgo del producto / riesgos específicos”.
- Agregar columnas de estructura/responsable/empresa.

#### 2.4 Gas natural (`matpel_otros`)

- Aplicar el mismo tratamiento que GLP: vehículos múltiples con conductor/propietario.
- Conservar los campos de estructura/responsable/empresa existentes.
- Detalle/PDF alineados con GLP.

**Criterio de aceptación:** combustible y químico permiten elegir vehículo o estructura; GLP y gas natural conservan su bloque de estructura/empresa y agregan vehículos múltiples con conductor/propietario. Los 4 muestran el bloque correcto en detalle/PDF.

---

### Fase 3 — APH y traslados (2 j)

**Depende de:** fase 1 (parcial).

> **Alcance:** “todos los reportes de traslado” incluye los 4 APH **y** el reporte de Traslado Rutinario (`pre_hospitalario`), que hoy también es un traslado realizado y no tiene temperatura, Glasgow ni firma.

Formulario:

1. En `_paciente_aph.html` o en un partial nuevo `_signos_vitales_aph.html`:
   - Agregar **Temperatura** al lado de Frecuencia Respiratoria (grid de 4 columnas: TA, FC, FR, Temperatura).
   - Agregar **Escala de Glasgow** (apertura ocular, respuesta verbal, respuesta motora y total calculado) en:
     - `aph_traslado`
     - `aph_interhospitalario`
     - `aph_sin_traslado`
     - `pre_hospitalario`
     - **No** en `aph_no_traslado`.
2. Firmas:
   - `aph_traslado`, `aph_interhospitalario` y `pre_hospitalario`: agregar bloque “Médico que recibe” con `medico_recibe`, `medico_cedula`, `medico_msds` y checkbox `medico_firma` (“Firma registrada”).
   - `aph_no_traslado`: agregar bloque “Constancia del paciente” con `rechazo_nombre`, `rechazo_cedula` y checkbox `rechazo_firma`.
   - `aph_sin_traslado`: solo temperatura y Glasgow; sin firma nueva.
3. Mantener los campos ya existentes de rechazo en los traslados realizados (no romper el flujo actual).
4. En `pre_hospitalario` usar los nombres de campos propios del modelo (`signos_vitales_tension`, `signos_vitales_pulso`, `signos_vitales_fr`) y agregar las columnas nuevas.

Detalle/PDF:

- Mostrar temperatura y Glasgow.
- Mostrar bloque de firma con nombre, cédula y estado.
- No mostrar Glasgow en traslado no realizado.

**Criterio de aceptación:** los 4 APH y el Traslado Rutinario guardan y muestran temperatura; Glasgow aparece en 4 de 5 (todos menos no realizado); las firmas se reflejan en detalle y PDF.

---

### Fase 4 — Incendios: ajustes de pérdidas (0,5 j)

**Depende de:** ninguna (independiente de fase 1).

Cambios por subtipo:

| Subtipo | Cambio |
|---|---|
| `incendio_electrico` | Eliminar “% Pérdida por Humo” y “% Pérdida Total” del formulario, `REPORT_FIELDS_MAP`, detalle y PDF. |
| `incendio_desechos` | Agregar “% Pérdida por Fuego” en formulario, map, detalle y PDF. |
| `incendio_vegetacion` | Eliminar humo y total. |
| `incendio_arbol` | Eliminar humo y total. |

Archivos:

- `_incendio_params_electrico.html`, `_incendio_params_desechos.html`, `_incendio_params_vegetacion.html`, `_incendio_params_arbol.html`.
- `app/routes/reportes.py` (`REPORT_FIELDS_MAP`).
- `detalle.html` y `_detalle_incendio.html`.
- `reporte_pdf.html` y `pdf_service.py` (si lista esos campos).

**Nota:** las columnas se conservan en BD para no perder datos históricos; solo se ocultan en formularios nuevos. En detalle/PDF se puede decidir si se muestran cuando tengan valor (recomendado: sí, para históricos).

**Criterio de aceptación:** los 4 subtipos muestran exactamente los campos solicitados y los reportes históricos no se rompen.

---

### Fase 5 — Siniestros viales (2 j)

**Depende de:** fase 1.

#### 5.1 Consolidación

- Crear los tipos canónicos `siniestro_vial_con_lesionado` y `siniestro_vial_sin_lesionado` en:
  - `REPORT_MODEL_MAP` → `ReporteRescateColision`.
  - `REPORT_PREFIX_MAP` (`SIN_L`, `SIN_S`).
  - `REPORT_TITLE_MAP`.
  - `REPORT_FIELDS_MAP`.
  - Menús (`base.html`, `bombero/historial.html`).
- Mantener los 4 tipos antiguos como legacy, ocultos de menús, para enlaces históricos.
- Ajustar `Reporte.tipo_especifico` para devolver `siniestro_vial_*` cuando `subtipo_rescate` empiece con `siniestro_vial_`.
- En `crear_reporte`, agregar una rama explícita para `siniestro_vial_*` que asigne `subtipo_rescate` (el bloque actual solo reconoce `rescate_colision_*` y `rescate_volcamiento_*`).
- Ajustar dashboard y `pdf_service.NOMBRE_SERVICIO`.

#### 5.2 Formulario

- Selector `tipo_siniestro`: Colisión / Volcamiento / Choque / Otro + `tipo_siniestro_otro`.
- Sección de vehículos: `_vehiculos_involucrados.html` con `mostrar_carga=False`, múltiples unidades, conductor y propietario.
- Sección de lesionados: `_personas_afectadas.html` solo para `con_lesionado` (nombre, cédula, edad, sexo, lesión, residencia).
- Conservar datos del custodio/responsable.
- Unidades: sección 3 con horas propias.

#### 5.3 Detalle/PDF

- Título “Siniestro Vial con Lesionado” / “sin Lesionado”.
- Mostrar tipo de siniestro.
- Tabla de vehículos involucrados con conductor/propietario.
- Tabla de lesionados (solo con lesionado).
- Mantener compatibilidad con los textos libres históricos.

**Criterio de aceptación:** se crean ambos siniestros, con múltiples vehículos, tipo de siniestro y lesionados cuando aplica; los 4 tipos antiguos siguen abriendo.

---

### Fase 6 — Rescates y nuevo formato de búsqueda (2,5 j)

**Depende de:** fase 1.

#### 6.1 Ascensor e inmueble

- En parámetros técnicos dejar **solo** “Material utilizado” (`despliegue_material_usado`).
- Quitar `tipo_servicio` y los campos de despliegue que no se piden (vehículos desplegados, cantidad de bomberos, conductor, jefe). Si el área operativa necesita `tipo_servicio`, confirmarlo antes de retirarlo.
- Agregar “Personas rescatadas” con `_personas_afectadas.html` (nombre, cédula, edad, lesión).
- Agregar `salida_ambulancia` (hora) en parámetros o en la sección de unidades.

#### 6.2 Persona tapiada

- Solo “Material utilizado”.
- Quitar `tipo_servicio` y los campos de despliegue no solicitados.
- Personas rescatadas.
- `motivo_tapiado` (texto).
- `salida_ambulancia`.

#### 6.3 Persona golpeada

- Solo “Material utilizado”.
- Quitar `tipo_servicio` y los campos de despliegue no solicitados.
- Personas rescatadas.
- `motivo_golpe` (texto).
- `salida_ambulancia`.
- Checkbox `fue_vehiculo_movimiento`.
- Si está marcado: mostrar `_vehiculos_involucrados.html` (uno o varios) con datos del conductor.

#### 6.4 Persona caída en altura

- Agregar `salida_ambulancia` y `salida_primera_maquina`.
- Agregar “Material utilizado” (`despliegue_material_usado`).
- Mantener los datos actuales de la persona/lesionado.
- Decidir si se muestran secciones 3–5 (recomendado: no, solo horas y material explícitos).

#### 6.5 Cadáver

- Agregar “Material utilizado”.
- Mantener datos del cadáver.

#### 6.6 Nuevo formato “Operaciones de búsqueda y rescate”

- Nuevo modelo `ReporteBusquedaRescate` (`reportes_busqueda_rescate`):
  - `lugar_busqueda` (`areas_escarpadas`, `cuerpos_agua`, `otros`).
  - `lugar_busqueda_otro`.
  - `material_usado`.
  - Campos comunes heredados.
- Nuevo tipo `rescate_busqueda` en mapas, títulos, prefijo (`RES_BUSQ`), menús, formulario, detalle, PDF y dashboard.
- Excluir `rescate_busqueda` de la rama de subtipos de rescate especializado en `crear_reporte` (hoy todo `rescate_*` que no sea colisión/volcamiento asigna `subtipo_rescate`, campo que este modelo no tiene).
- Cabecera estándar con unidades (sección 3), personal (4) y organismos (5) — confirmar en pregunta 8.
- Parámetros técnicos: selector de lugar + “Otros” con texto, material usado.
- Personas: `_personas_afectadas.html` con nombre, cédula, edad, lesión.
- `incluye_secciones_operativas = True` para este tipo.

**Criterio de aceptación:** los 6 rescates existentes muestran solo lo pedido y el nuevo formato se crea, detalla y exporta.

---

### Fase 7 — Fauna y retiro de Baldeo (1 j)

#### 7.1 Fauna

- `servicio_insectos`: `tipo_insecto` con `onchange="manejarOtros(this, 'tipo_insecto_otro')"` e input.
- `servicio_animal`: `tipo_animal` con el mismo patrón.
- Verificar guardado en `tipo_insecto` / `tipo_animal` (el backend ya resuelve `_otro`).

#### 7.2 Baldeo

Puntos a retirar:

- `app/templates/base.html` (menú).
- `app/templates/bombero/historial.html` (menú).
- `app/templates/admin/dashboard.html` (KPI, agrupación y color).
- `app/routes/main.py` (import, suma de litros y referencias).
- `app/routes/reportes.py` (mapas de creación, título, prefijo y campos).
- `crear.html` (sección 2.10).
- Opcional: dejar detalle/PDF para históricos.

Recomendación:

- Quitar `servicio_baldeo` de `REPORT_MODEL_MAP` para que `/crear/servicio_baldeo` no sea accesible; conservar modelo/tabla y la rama de detalle/PDF.
- Si se elimina también de detalle/PDF, los históricos quedarían inaccesibles; no recomendado.

**Criterio de aceptación:** Baldeo no aparece en menús ni dashboard; la URL de creación ya no funciona; un reporte histórico (si existiera) sigue visible.

---

### Fase 8 — Numeración, PDF, detalle y dashboard (2 j)

#### 8.1 Numeración

**Formulario (`crear.html`):**

- La sección 6 (“Descripción de la Actuación / Observaciones Generales”) se muestra siempre, pero las secciones 3–5 se ocultan para `rescate_caida` y `rescate_cadaver`. Hoy el formulario salta de 2 a 6.
- Renumerar con condicionales o contador: para caída/cadáver, observaciones debe ser 3; para el resto, 6. Si en el futuro se muestran 3–5 en caída/cadáver, volverá a 6.

**PDF (`reporte_pdf.html`):**

- Reemplazar los números fijos por un contador dinámico con `{% set ns = namespace(sec=2) %}` e incrementos antes de cada sección.
- Para `rescate_caida` y `rescate_cadaver`, decidir:
  - Si no se muestran 3–5: observaciones = 3, firmas = 4.
  - Si se muestran: mantener 3–5 y observaciones = 6.
- Evitar la expresión actual `{% if ... %}3{% else %}6{% endif %}`.

**Detalle (`detalle.html`):**

- Aplicar el mismo criterio de numeración dinámica.
- Verificar que no queden saltos cuando se ocultan secciones.

#### 8.2 PDF y DTO

- Actualizar `SECCIONES_ESPECIFICAS` con los campos nuevos:
  - MATPEL: origen, estructura, responsable, riesgo, vehículos.
  - APH: temperatura, Glasgow, firmas.
  - Siniestros: tipo, vehículos, lesionados.
  - Rescates: material, personas, motivos, horas.
  - Búsqueda: lugar, material, personas.
- Actualizar `NOMBRE_SERVICIO`.
- Ampliar `serializar_reporte()` para incluir vehículos involucrados, personas, firmas y horas nuevas.
- Actualizar `reporte_pdf.html` con las tablas/bloques correspondientes.
- Verificar que WeasyPrint y xhtml2pdf rendericen sin desbordes.

#### 8.3 Dashboard

- Quitar Baldeo de agrupaciones, colores y KPIs de agua.
- Agregar `siniestro_vial_*` y `rescate_busqueda` a las agrupaciones.
- Ajustar `main.py` para no importar `ReporteServicioBaldeo`.

**Criterio de aceptación:** todos los tipos renderizan detalle y PDF sin saltos de numeración; el dashboard no muestra Baldeo y sí los tipos nuevos.

---

### Fase 9 — QA, migración y cierre (1,5 j)

1. **Migración:**
   - Copiar `bomberos.db` a un directorio temporal.
   - Ejecutar `python migrate_db.py` dos veces; verificar columnas y tablas nuevas.
   - Verificar que los 3 reportes existentes abren en detalle y PDF.
   - Regenerar `postgres_schema.sql`.
2. **Pruebas funcionales:** crear un reporte por cada tipo (mínimo 30) y verificar:
   - guardado correcto,
   - detalle 200,
   - PDF 200,
   - campos nuevos visibles,
   - campos eliminados ocultos.
3. **Pruebas específicas:**
   - MATPEL vehículo vs estructura; múltiples vehículos.
   - APH 4 variantes + Traslado Rutinario; Glasgow y firmas.
   - Incendios 7 subtipos; pérdidas correctas.
   - Siniestros con/sin lesionado; tipo de siniestro y lesionados.
   - Rescates 6 + búsqueda; personas, material y horas.
   - Fauna “Otro” con texto.
   - Baldeo ausente.
4. **Calidad de código:**
   - `python -m pyflakes app config.py run.py`
   - `python -m compileall app`
   - Revisar que no queden imports sin usar (Baldeo, `ReporteServicioBaldeo`, `vehiculo_afecto`, etc.).
5. **Regresión visual:** comparar PDF de los 3 reportes históricos antes/después.

---

## 5. Cambios de base de datos

### 5.1 Columnas nuevas (`COLUMNAS_NUEVAS`)

```python
COLUMNAS_NUEVAS = {
    # ... columnas existentes ...

    'reporte_vehiculos_actuantes': {
        'tipo_unidad': 'VARCHAR(30)',
        'nombre_unidad_libre': 'VARCHAR(150)',
        'conductor_cedula': 'VARCHAR(20)',
        'hora_regreso': 'TIME',
        'orden': 'INTEGER',
    },
    'reportes_matpel_combustible': {
        'origen_derrame': 'VARCHAR(20)',
        'riesgo_producto': 'VARCHAR(150)',
        'tipo_estructura': 'VARCHAR(100)',
        'responsable_nombre': 'VARCHAR(150)',
        'responsable_cedula': 'VARCHAR(20)',
        'responsable_telefono': 'VARCHAR(30)',
        'empresa_nombre': 'VARCHAR(150)',
        'empresa_rif': 'VARCHAR(30)',
    },
    'reportes_matpel_quimico': {
        'origen_derrame': 'VARCHAR(20)',
        'tipo_estructura': 'VARCHAR(100)',
        'responsable_nombre': 'VARCHAR(150)',
        'responsable_cedula': 'VARCHAR(20)',
        'responsable_telefono': 'VARCHAR(30)',
        'empresa_nombre': 'VARCHAR(150)',
        'empresa_rif': 'VARCHAR(30)',
    },
    # GLP y gas natural ya tienen propietario_nombre, propietario_rif_ci y
    # empresa_distribuidora; no requieren columnas nuevas de responsable.
    'reportes_pre_hospitalario': {
        'signos_vitales_temperatura': 'VARCHAR(10)',
        'glasgow_apertura_ocular': 'INTEGER',
        'glasgow_respuesta_verbal': 'INTEGER',
        'glasgow_respuesta_motora': 'INTEGER',
        'glasgow_total': 'INTEGER',
        'medico_recibe': 'VARCHAR(150)',
        'medico_cedula': 'VARCHAR(20)',
        'medico_msds': 'VARCHAR(50)',
        'medico_firma': 'BOOLEAN',
    },
    'reportes_rescate_especializado': {
        'motivo_tapiado': 'TEXT',
        'motivo_golpe': 'TEXT',
        'fue_vehiculo_movimiento': 'BOOLEAN',
        'salida_ambulancia': 'TIME',
        'salida_primera_maquina': 'TIME',
    },
    'reportes_rescate_colision': {
        'tipo_siniestro': 'VARCHAR(30)',
        'tipo_siniestro_otro': 'VARCHAR(100)',
    },
}
```

**Nota:** `material_usado` de rescates se resuelve con la columna existente `despliegue_material_usado` (se muestra como “Material utilizado”), para no duplicar campos. Si se prefiere un nombre semántico nuevo, agregar `material_usado TEXT` y migrar el valor.

### 5.2 Tablas nuevas

**`reporte_vehiculos_involucrados`**

```text
id                  INTEGER PK
reporte_id          INTEGER FK reportes(id) ON DELETE CASCADE
orden               INTEGER
marca               VARCHAR(50)
modelo              VARCHAR(50)
color               VARCHAR(30)
placa               VARCHAR(20)
tipo                VARCHAR(50)
uso                 VARCHAR(100)
serial_carroceria   VARCHAR(100)
serial_motor        VARCHAR(100)
anio                VARCHAR(10)
condicion           VARCHAR(100)
valor               NUMERIC(14, 2)
perdidas            NUMERIC(14, 2)
aseguradora         VARCHAR(150)
conductor_nombre    VARCHAR(150)
conductor_cedula    VARCHAR(20)
conductor_telefono  VARCHAR(30)
conductor_edad      INTEGER
propietario_nombre  VARCHAR(150)
propietario_cedula  VARCHAR(20)
propietario_telefono VARCHAR(30)
propietario_edad    INTEGER
valor_carga         NUMERIC(14, 2)
perdida_carga       NUMERIC(14, 2)
aseguradora_carga   VARCHAR(150)
```

**`reportes_busqueda_rescate`**

```text
id                  INTEGER PK FK reportes(id) ON DELETE CASCADE
lugar_busqueda      VARCHAR(50)
lugar_busqueda_otro VARCHAR(150)
material_usado      TEXT
```

### 5.3 Migración de datos

| Dato | Acción |
|---|---|
| 2 filas de `reporte_vehiculos_actuantes` | Conservar. Rellenar `tipo_unidad` según `vehiculos.tipo` (Ambulancia → ambulancia; máquina → primera_maquina). |
| 2 reportes GLP + 1 químico | No migrar; el detalle/PDF debe seguir leyendo las columnas legacy. |
| JSON de vehículos históricos | No migrar masivamente; fallback de lectura. |
| Baldeo | 0 filas; conservar tabla. |
| `vehiculo_id` NOT NULL en SQLite | Reconstrucción idempotente de la tabla (fase 1). |

### 5.4 Compatibilidad

- Las columnas viejas de MATPEL (`vehiculo_marca`, `vehiculo_modelo`, etc.) se conservan.
- `vehiculos_afectados_json` y `vehiculos_involucrados_json` se conservan.
- Los tipos legacy de siniestros se conservan en el mapa de lectura.
- `ReporteServicioBaldeo` se conserva para históricos.

---

## 6. Matriz de cambios por formato

| Formato | Cambios principales | Modelo/BD | Formulario | Detalle/PDF |
|---|---|---|---|---|
| MATPEL combustible | Quitar vehículo causante; origen vehículo/estructura; múltiples vehículos; riesgo | Columnas nuevas + tabla vehículos | Sección 2.2 | Bloques nuevos |
| GLP | Múltiples vehículos con conductor/propietario | Tabla vehículos | Sección 2.1 | Tabla vehículos |
| Químico | Origen vehículo/estructura; renombrar sustancia | Columnas nuevas + tabla vehículos | Sección 2.3 | Bloques nuevos |
| Gas natural | Igual que GLP | Tabla vehículos | Sección 2.4 | Tabla vehículos |
| APH traslado | Temperatura, Glasgow, firma médico | Sin cambios | Sección APH | Mostrar campos |
| APH no traslado | Temperatura, firma paciente; sin Glasgow | Sin cambios | Sección APH | Mostrar campos |
| APH interhospitalario | Temperatura, Glasgow, firma médico | Sin cambios | Sección APH | Mostrar campos |
| APH sin traslado | Temperatura, Glasgow | Sin cambios | Sección APH | Mostrar campos |
| Traslado rutinario | Temperatura, Glasgow, firma médico | Columnas nuevas | Sección APH | Mostrar campos |
| Incendio eléctrico | Quitar humo/total | Sin cambios | Partial eléctrico | Ocultar |
| Incendio desechos | Agregar fuego | Sin cambios | Partial desechos | Mostrar |
| Incendio vegetación/árbol | Quitar humo/total | Sin cambios | Partial respectivo | Ocultar |
| Siniestros | 2 tipos canónicos, selector, vehículos, lesionados | Columnas + tabla vehículos | Secciones nuevas | Tablas nuevas |
| Ascensor/inmueble | Solo material, rescatados, hora ambulancia | Sin cambios | Simplificar | Mostrar |
| Tapiada | Material, rescatados, motivo, hora | `motivo_tapiado` | Simplificar | Mostrar |
| Golpeada | Material, rescatados, motivo, hora, vehículo condicional | `motivo_golpe`, `fue_vehiculo_movimiento` | Simplificar | Mostrar |
| Caída altura | Horas ambulancia/primera máquina, material | Horas | Agregar | Mostrar |
| Cadáver | Material | Sin cambios | Agregar | Mostrar |
| Búsqueda y rescate | Formato nuevo | Tabla nueva | Sección nueva | Sección nueva |
| Fauna | “Otros” con texto | Sin cambios | Inputs | Mostrar valor |
| Baldeo | Retirar de operación | Conservar | Quitar | Conservar histórico |

---

## 7. Numeración y PDF

### 7.1 Problema actual

En `reporte_pdf.html`:

```jinja
{% if dto.tipo_reporte in ('rescate_caida', 'rescate_cadaver') %}3{% else %}6{% endif %}.
Observaciones Generales y Relato Operacional
```

Para caída/cadáver se omiten las secciones 3, 4 y 5, pero la sección de observaciones se rotula como 3 y las firmas como 7. Resultado: 2 → 3 → 7.

### 7.2 Solución propuesta

Usar un contador dinámico:

```jinja
{% set ns = namespace(sec=2) %}
...
{% set ns.sec = ns.sec + 1 %}
<td class="titulo-seccion">{{ ns.sec }}. Vehículos y Unidades Actuantes</td>
...
{% set ns.sec = ns.sec + 1 %}
<td class="titulo-seccion">{{ ns.sec }}. Observaciones Generales y Relato Operacional</td>
...
<td class="titulo-seccion">{{ ns.sec + 1 }}. Firmas</td>
```

Aplicar el mismo patrón en `detalle.html`. Así, si en el futuro se agrega o quita una sección, la numeración se ajusta sola.

### 7.3 Secciones 3–5 en caída/cadáver

Dos opciones:

- **A (mínima):** mantenerlas ocultas y renumerar 3 = observaciones, 4 = firmas.
- **B (recomendada si se agregan unidades/material):** mostrarlas cuando existan datos y mantener 6 = observaciones.

La fase 6 define si caída/cadáver usan sección 3. La decisión debe quedar cerrada antes de la fase 8.

---

## 8. Preguntas a confirmar antes de codificar

1. **Siniestro vial sin lesionado:** ¿se confirma un reporte hermano “Siniestro Vial sin Lesionado”, sin sección de lesionados, o se maneja como el mismo reporte con un checkbox “hubo lesionados”?  
   *Recomendación:* dos tipos canónicos, como se plantea en D7.

2. **Hora de salida por unidad:** ¿todas las unidades de la cabecera (Primera, Segunda, Ambulancia, adicional) tendrán su propia hora de salida?  
   *Recomendación:* sí, en la sección 3; la hora global de cabecera se conserva como salida general.

3. **Subformularios reutilizables:** ¿se aprueba la tabla `reporte_vehiculos_involucrados` + macro compartida, en lugar de seguir usando JSON y campos sueltos?  
   *Recomendación:* sí; el JSON queda solo como lectura histórica.

4. **Firmas APH:** ¿la firma es una casilla de constancia (“firma registrada”) o se requiere captura/archivo de imagen de la firma?  
   *Impacto:* si es imagen, hay que definir almacenamiento, tamaño y cómo incrustarla en el PDF.

5. **Baldeo:** ¿se conservan los datos históricos en modo lectura o se elimina también la tabla?  
   *Recomendación:* conservar tabla y detalle/PDF; retirar solo la creación y los KPIs.

6. **Personas rescatadas:** ¿basta con nombre, cédula, edad, sexo y “lesión” en texto libre, reutilizando `reporte_personas_afectadas`?  
   *Recomendación:* sí; no crear tabla nueva.

7. **GLP / gas natural:** la sección de vehículos, ¿se refiere al vehículo que causó la fuga, al que transportaba el cilindro, o a ambos?  
   *Impacto:* define las etiquetas y si se permiten varios vehículos.

8. **Búsqueda y rescate:** ¿debe incluir las secciones 3 (unidades), 4 (personal) y 5 (organismos), o solo cabecera, lugar, personas y material?  
   *Recomendación:* incluir 3–5 para que sea un reporte completo.

9. **Incendios con campos eliminados:** en reportes históricos que ya tengan “pérdida por humo/total”, ¿se siguen mostrando en detalle/PDF o se ocultan siempre?  
   *Recomendación:* mostrarlos solo si tienen valor, para no perder información.

10. **Nombre de la sustancia (químico):** ¿se cambia solo la etiqueta visible o también el nombre de la columna `tipo_combustible`/`nombre_sustancia`?  
    *Recomendación:* solo la etiqueta; la columna `nombre_sustancia` ya existe y no requiere migración.

---

## 9. Pruebas y criterios de aceptación

### 9.1 Pruebas de migración

- [ ] `python migrate_db.py` sobre copia de `bomberos.db` sin errores.
- [ ] Ejecutarlo dos veces; no duplica columnas ni datos.
- [ ] `PRAGMA table_info(reporte_vehiculos_actuantes)` muestra `vehiculo_id` nullable.
- [ ] Las tablas nuevas existen y tienen FK a `reportes` con `ON DELETE CASCADE`.
- [ ] Los 3 reportes históricos abren en detalle y PDF.

### 9.2 Pruebas funcionales

- [ ] Cabecera: 4 unidades, una libre, con horas distintas.
- [ ] MATPEL combustible: origen vehículo y origen estructura; 2 vehículos; riesgo.
- [ ] MATPEL GLP: 2 vehículos con conductor/propietario.
- [ ] MATPEL químico: origen vehículo/estructura; “Nombre de la sustancia”.
- [ ] Gas natural: 2 vehículos.
- [ ] APH traslado: temperatura, Glasgow, firma médico.
- [ ] APH no traslado: temperatura, firma paciente, sin Glasgow.
- [ ] APH interhospitalario: temperatura, Glasgow, firma médico.
- [ ] APH sin traslado: temperatura, Glasgow.
- [ ] Traslado rutinario: temperatura, Glasgow, firma médico.
- [ ] Incendio eléctrico: sin humo/total.
- [ ] Incendio desechos: con pérdida por fuego.
- [ ] Incendio vegetación/árbol: sin humo/total.
- [ ] Siniestro con lesionado: tipo, 2 vehículos, 2 lesionados.
- [ ] Siniestro sin lesionado: sin sección de lesionados.
- [ ] Ascensor/inmueble: material, rescatados, hora ambulancia.
- [ ] Tapiada: material, rescatados, motivo, hora.
- [ ] Golpeada: material, rescatados, motivo, hora, vehículo condicional.
- [ ] Caída: horas y material.
- [ ] Cadáver: material.
- [ ] Búsqueda: lugar, “Otros”, material, personas.
- [ ] Fauna: “Otro” guarda el texto.
- [ ] Baldeo: no aparece en menús/dashboard; creación no disponible.

### 9.3 Pruebas técnicas

- [ ] `python -m pyflakes app config.py run.py` sin errores.
- [ ] `python -m compileall app` sin errores.
- [ ] Detalle 200 y PDF 200 para cada tipo.
- [ ] PDF de históricos sin cambios de datos.
- [ ] Sin saltos de numeración en formulario, detalle y PDF.
- [ ] `postgres_schema.sql` regenerado.

---

## 10. Orden de entrega y estimación

| Fase | Contenido | Depende de | Tamaño |
|---|---|---|---:|
| 0 | Decisiones + respaldo | — | 0,5 j |
| 1 | Unidades, vehículos, personas, “Otros” | 0 | 3 j |
| 2 | MATPEL | 1 | 2 j |
| 3 | APH y Traslado Rutinario | 1 | 2 j |
| 4 | Incendios | — | 0,5 j |
| 5 | Siniestros | 1 | 2 j |
| 6 | Rescates + búsqueda | 1 | 2,5 j |
| 7 | Fauna + Baldeo | — | 1 j |
| 8 | Numeración, PDF, detalle, dashboard | 2–7 | 2 j |
| 9 | QA y migración | 2–8 | 1,5 j |

**Total:** ~17 jornadas. Con trabajo paralelo (fases 2, 3, 4, 5 y 7 tras la fase 1), se puede reducir a ~13-14 jornadas de calendario.

**Sugerencia de entrega incremental:**

1. Fase 1 + 4 + 7 (infraestructura y ajustes simples).
2. Fase 2 + 3 (MATPEL y APH).
3. Fase 5 + 6 (siniestros y rescates).
4. Fase 8 + 9 (PDF, numeración y QA).

---

## 11. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Reconstrucción de tabla en SQLite | Pérdida de datos si falla | Respaldo previo, transacción, prueba en copia, script idempotente |
| Duplicación de unidades cabecera/sección 3 | Datos inconsistentes | Una sola tabla y una sola fuente; la cabecera solo agrega filas |
| PDF con demasiadas columnas | Desborde en A4 | Tablas compactas, fuentes pequeñas, probar WeasyPrint y xhtml2pdf |
| Formulario único muy grande | Difícil mantenimiento | Partials/macros por bloque; no seguir agregando HTML inline |
| Históricos con JSON | Pérdida de visualización | Fallback de lectura; no borrar columnas |
| Nombres de tipos legacy | Enlaces y dashboard rotos | Mantener alias legacy en mapas y `tipo_especifico` |
| Cambios en `postgres_schema.sql` | Producción desalineada | Regenerar y revisar antes de desplegar |

---

## 12. Fuera de alcance (salvo confirmación)

- Rediseño visual general del sistema.
- Migración a Alembic.
- Borrado físico de datos históricos.
- Firma digital con valor legal/certificado.
- API externa o integración con otros sistemas.
- Cambios en autenticación, usuarios o permisos.

---

**Fin del documento.**
