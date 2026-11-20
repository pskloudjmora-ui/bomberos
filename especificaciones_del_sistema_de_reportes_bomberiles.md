# Especificaciones y Reglas de Negocio - Sistema de Reportes

Este documento define los requerimientos funcionales, reglas de validación, visualización en impresión y estructura de formularios para el sistema de gestión de reportes operativos.

---

## 1. Reglas Generales (Aplica a TODOS los reportes)

### 1.1 Información de Cabecera
- **Clase de aviso:**
  - Renombrar la opción `"Radial"` a `"Radio Transmisor"`.
  - Renombrar la opción `"Personal"` a `"Verbal"`.
  - Agregar la opción `"Ocasional"`.
- **Formato de horas:**
  - Todas las horas del sistema deben manejarse estrictamente en **formato de 24 horas** (`HH:mm` o `HH:mm:ss` según corresponda, ej. `21:00`, `22:50:20`).
- **Itinerario:**
  - Agregar un campo de texto (`input` / `textarea`) en la cabecera para registrar el **Itinerario de las unidades**.
- **Cuadrante de Paz:**
  - Agregar un campo de texto en la cabecera para registrar el **Cuadrante de Paz** correspondiente a la zona del servicio.
- **Tiempos de salida de unidades:**
  - Las horas de salida deben soportar y registrar **segundos** (agregando un desfase/margen de `20` o `40` segundos respecto a la hora de recepción de llamada, ej. llamada a las `22:50` $\rightarrow$ salida `22:50:20`).

### 1.2 Módulo de Estadísticas (Feature adicional)
- Implementar estadísticas de servicios filtrables/agrupadas por **Cuadrante de Paz** y rango de fechas (ej. *"En el cuadrante de paz 046 se atendieron 123 servicios en el mes"*).

### 1.3 Lógica Condicional e Impresión (Regla Global)
- **Visibilidad en formulario e impresión:** Todo campo opcional o dependiente de un `checkbox` **NO debe mostrarse en el formulario ni renderizarse en la vista de impresión/PDF** si el `checkbox` padre no está marcado.

---

## 2. Reglas por Tipo de Reporte

### 2.1 Incendios de Estructura
- **Despacho de Unidades (Cabecera / Horas):**
  - Permitir un renglón independiente con su propia hora de salida (`HH:mm:ss`) por cada unidad actuante:
    - `Salida Primera Máquina`
    - `Salida Segunda Máquina`
    - `Salida Ambulancia`
    - Permitir agregar dinámicamente **otra unidad adicional** en caso necesario (ej. *Salida de moto institucional*).
- **Parámetros Técnicos:**
  - **Clase de incendio:** Reemplazar la lista actual (`"Primera alarma"`, `"Segunda alarma"`, etc.) por **Clases**: `Primera clase`, `Segunda clase`, `Tercera clase`.
  - **Tipo de estructura (reemplaza a "Intensidad"):** Eliminar el campo `"Intensidad"` (`1era`, `2da`, etc.) y sustituirlo por un selector de **Tipo de Estructura** con opciones como: `Residencial`, `Industrial`, `Comercial`, `Recreacional`, entre otras.
  - **Propagación:** Junto a `"Litros de agua utilizados"`, mantener el check de propagación. El cuadro de texto descriptivo **solo debe aparecer (en UI e impresión) si el check está marcado**.
  - **Equipos contra incendios (Lógica en cascada):**
    1. Check: `"El inmueble poseía equipos"`. Si no se marca, no se muestra nada más ni aparece en impresión.
    2. Si se marca `"El inmueble poseía equipos"`, desplegar el check: `"Fueron utilizados"`.
    3. Si se marca `"Fueron utilizados"`, desplegar dos campos de texto:
       - `"¿Por quién fue usado?"` (Nombre).
       - `"Tipo de equipo de extinción"` (entrada manual de texto).
- **Nuevas Secciones en Parámetros Técnicos:**
  - **Información del Inmueble:**
    - `Descripción` (Opciones: `Alquilada`, `Propiedad`, `A Cuido`)
    - `Propietario`
    - `C.I. o RIF`
    - `Teléfono`
    - `Valor Aprox. del Inmueble`
    - `Valor Aprox. de Pérdidas`
    - `Firma Aseguradora`
  - **Información del Mueble:**
    - `Propietario`
    - `C.I. o RIF`
    - `Valor Aprox. del Mueble`
    - `Valor Aprox. de Pérdidas`
    - `Firma Aseguradora`
    - `Condición`
    - `El lugar quedó a cargo de`

---

### 2.2 Incendio de Vehículos
- **Despacho de Unidades:**
  - Igual que en *Incendios de Estructura*: renglones independientes con segundos (`HH:mm:ss`) para `Primera Máquina`, `Segunda Máquina`, `Ambulancia` y opción para agregar unidad adicional (ej. moto institucional).
- **Parámetros Técnicos:**
  - **Clase de incendio:** Cambiar listado a `Primera clase`, `Segunda clase`, `Tercera clase`.
  - **Eliminar** el campo `"Intensidad"`.
  - **Propagación:** El cuadro de texto solo se muestra en UI e impresión si se marca el check.
  - **Equipos contra incendios:** Misma lógica condicional en cascada que en *Incendios de Estructura* (`Poseía equipos` $\rightarrow$ `Fueron utilizados` $\rightarrow$ `¿Por quién fue usado?` + `Tipo de equipo`), **pero omitiendo la palabra "Inmueble"** en las etiquetas (ej. `"Poseía equipos"`).
- **Datos del Vehículo Afectado:**
  - Incluir botón **"Agregar vehículo"** (similar al de `"Vehículos bomberiles actuantes"`) para permitir registrar múltiples vehículos afectados (`Información del Vehículo (1)`, `(2)`, etc.).
  - Campos requeridos por cada vehículo:
    - `Marca`, `Modelo`, `Color`, `Placa`
    - `Serial Motor`, `Año`, `Valor del Vehículo`
    - `Valor Aprox. de Pérdidas`, `Firma Aseguradora`
    - `Propietario`, `C.I.`
    - `Conductor`, `C.I.`
    - `Valor de la Carga`, `Pérdida Aprox. de Carga`, `Firma Aseguradora de la Carga`
    - `Condición`

---

### 2.3 Incendios de Equipos Eléctricos
- **Campos a ELIMINAR (no deben aparecer):**
  - `"Lugar de desarrollo"`
  - `"Clase"`
  - `"Intensidad"`
  - `"Presunto origen"`
  - `"Propagación"`
  - `"El inmueble poseía equipos contra incendios"` (y sus dependientes)
- **Sección a AGREGAR:**
  - **Información del Sistema Eléctrico Público:**
    - `Tipo`
    - `Capacidad`
    - `Uso`
    - `Serial`
    - `Propiedad de`
    - `RIF`

---

### 2.4 Incendios de Desechos Sólidos
- **Despacho de Unidades:**
  - Renglones independientes con segundos (`HH:mm:ss`) para `Primera Máquina`, `Segunda Máquina` y opción para agregar otra unidad (ej. moto institucional). *(No incluye ambulancia por defecto).*
- **Campos a ELIMINAR (no deben aparecer):**
  - `"Lugar de desarrollo"`
  - `"Clase"`
  - `"Intensidad"`
  - `"Presunto origen"`
  - `"Propagación"`
  - `"El inmueble poseía equipos contra incendios"`
  - `"% de pérdida por fuego"`
- **Sección a AGREGAR:**
  - **Información del Desperdicio:**
    - `Materia Prima`
    - `Cantidad`
    - `Recuperable` (Opciones: `Sí` / `No`)

---

### 2.5 Incendio de Vegetación
- **Despacho de Unidades:**
  - Solo contempla `Primera Máquina` y `Segunda Máquina` (con segundos `HH:mm:ss`). **No** se incluye ambulancia.
- **Campos a ELIMINAR (no deben aparecer):**
  - `"Lugar de desarrollo"`
  - `"Clase"`
  - `"Intensidad"`
  - `"Presunto origen"`
  - `"Propagación"`
  - `"El inmueble poseía equipos contra incendios"`
  - `"% de pérdida por fuego"`

---

### 2.6 Incendio de Árbol
- **Despacho de Unidades:**
  - Solo contempla `Primera Máquina` (con segundos `HH:mm:ss`).
- **Campos a ELIMINAR (no deben aparecer):**
  - `"Lugar de desarrollo"`
  - `"Clase"`
  - `"Intensidad"`
  - `"Presunto origen"`
  - `"Propagación"`
  - `"El inmueble poseía equipos contra incendios"`
  - `"% de pérdida por fuego"`
  - Sección `"Características del terreno"`
- **Campos a AGREGAR en Parámetros Técnicos:**
  - `Edad`
  - `Longitud`
  - `Circunferencia`
  - `Especie`

---

### 2.7 Apoyo por Incendios (Nuevo Formato)
- **Estructura del reporte:**
  - Mantiene la **Información de Cabecera** estándar.
  - En la sección de **Parámetros Técnicos**, incluir un selector desplegable: `"Tipo de incendio"`.
  - **Comportamiento dinámico:** Al seleccionar un tipo de incendio (ej. *Incendio de estructura*, *Incendio de vehículos*, etc.), se debe cargar/renderizar dinámicamente la plantilla de parámetros técnicos correspondiente a ese tipo de incendio.

---

### 2.8 Falsa Alarma (Nuevo Formato)
- **Alcance:** Aplica únicamente para reportes de **Incendios de Estructura** y **Incendios de Vehículos**.
- **Estructura del reporte:**
  - **Información de Cabecera** estándar.
  - Selector desplegable para indicar el tipo de incidente reportado: `Estructura` o `Vehículo`.
  - Sección de **Vehículos actuantes**.
  - Sección de **Funcionarios** (personal actuante).
  - Campo de texto amplio para **Descripción** de lo ocurrido.

---

## 3. Notas de Implementación para el Agente
- Antes de modificar cualquier formulario existente, revisa si los componentes de cabecera y unidades son compartidos entre reportes para aplicar las **Reglas Generales** de forma centralizada.
- Verifica siempre las hojas de estilo de impresión (`@media print`) o generadores de PDF para garantizar que los campos condicionales no marcados queden completamente ocultos y no dejen espacios en blanco.