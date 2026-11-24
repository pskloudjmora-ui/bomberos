"""
Servicio de generación de PDFs para los reportes operativos del Cuerpo de Bomberos.

El flujo es:
  1. serializar_reporte() convierte un objeto ORM en un DTO plano (dict) apto
     para la plantilla. Esto desacopla la base de datos del renderizador.
  2. generar_pdf_reporte() renderiza la plantilla reporte_pdf.html y la
     convierte a PDF usando WeasyPrint si está disponible (mejor fidelidad
     CSS) o xhtml2pdf como motor de respaldo puro-Python (sin dependencias
     nativas, ideal para Windows).

El logotipo se incrusta como Data URI (base64) directamente en el HTML para
que la conversión a PDF nunca dependa de servidores/URLs externas.
"""
import base64
import io
import os
from datetime import datetime
from functools import lru_cache

RUTA_LOGO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'imagen', 'logo-bomberos.png'
)

# Títulos legibles de cada tipo de servicio (se usan en el encabezado del PDF)
NOMBRE_SERVICIO = {
    'matpel_glp': 'CONTROL DE ESCAPE DE GAS LICUADO DE PETRÓLEO (GLP)',
    'matpel_combustible': 'DERRAME DE COMBUSTIBLE',
    'matpel_quimico': 'DERRAME DE SUSTANCIA QUÍMICA',
    'matpel_otros': 'CONTROL DE ESCAPE DE GAS NATURAL',
    'falsa_alarma': 'FALSA ALARMA POR INCENDIO',
    'pre_hospitalario': 'ATENCIÓN PRE-HOSPITALARIA / TRASLADO DE EMERGENCIA',
    'aph_traslado': 'APH - TRASLADO DE EMERGENCIA',
    'aph_no_traslado': 'APH - TRASLADO NO REALIZADO',
    'aph_interhospitalario': 'APH - TRASLADO INTERHOSPITALARIO',
    'aph_sin_traslado': 'APH - SIN TRASLADO',
    'incendio_estructura': 'INCENDIO DE ESTRUCTURA',
    'incendio_apoyo': 'APOYO POR INCENDIOS',
    'incendio_electrico': 'INCENDIO DE EQUIPO ELÉCTRICO',
    'incendio_vehiculo': 'INCENDIO DE VEHÍCULO',
    'incendio_desechos': 'INCENDIO DE DESECHOS SÓLIDOS',
    'incendio_vegetacion': 'INCENDIO DE VEGETACIÓN / FORESTAL',
    'incendio_arbol': 'INCENDIO DE ÁRBOL',
    'rescate_colision_con_lesionado': 'RESCATE COLISIÓN CON LESIONADO',
    'rescate_colision_sin_lesionado': 'RESCATE COLISIÓN SIN LESIONADO',
    'rescate_volcamiento_con_lesionado': 'RESCATE VOLCAMIENTO CON LESIONADO',
    'rescate_volcamiento_sin_lesionado': 'RESCATE VOLCAMIENTO SIN LESIONADO',
    'rescate_ascensor': 'RESCATE ESPECIALIZADO - ASCENSOR',
    'rescate_inmueble': 'RESCATE ESPECIALIZADO - INMUEBLE',
    'rescate_tapiada': 'RESCATE ESPECIALIZADO - TAPIADA',
    'rescate_golpeada': 'RESCATE ESPECIALIZADO - GOLPEADA',
    'rescate_caida': 'RESCATE DE PERSONA CAÍDA EN ALTURA',
    'rescate_cadaver': 'RESCATE DE CADÁVER',
    'servicio_agua': 'ABASTECIMIENTO DE AGUA',
    'servicio_insectos': 'CONTROL Y REUBICACIÓN DE INSECTOS',
    'servicio_animal': 'CONTROL DE ANIMAL DOMÉSTICO',
    'servicio_achicamiento': 'ACHICAMIENTO POR AGUAS ESTANCADAS',
    'servicio_baldeo': 'BALDEO DE AGUA',
    'servicio_piscinas': 'RECORRIDO POR PISCINAS Y BALNEARIOS',
    'servicio_lluvias': 'RECORRIDO POR LLUVIAS',
    'inspeccion_insectos': 'INSPECCIÓN - CONTROL Y REUBICACIÓN DE INSECTOS',
    'apertura_puerta': 'RECUPERACIÓN DE LLAVES / APERTURA DE PUERTA',
    'incendio_arbol_caido': 'CONTROL DE PELIGRO POR ÁRBOL CAÍDO',
    'siniestro_vial_con_lesionado': 'SINIESTRO VIAL CON LESIONADO',
    'siniestro_vial_sin_lesionado': 'SINIESTRO VIAL SIN LESIONADO',
    'busqueda_rescate': 'OPERACIONES DE BÚSQUEDA Y RESCATE',
}

# Título de la sección 2 (detalle específico) según el tipo de reporte
TITULO_SECCION_2 = {
    'matpel_glp': '2. DETALLE TÉCNICO - ESCAPE DE GLP (MATPEL)',
    'matpel_combustible': '2. DETALLE TÉCNICO - DERRAME DE COMBUSTIBLE (MATPEL)',
    'matpel_quimico': '2. DETALLE TÉCNICO - DERRAME DE SUSTANCIA QUÍMICA (MATPEL)',
    'matpel_otros': '2. DETALLE TÉCNICO - CONTROL DE GAS NATURAL (MATPEL)',
    'falsa_alarma': '2. DETALLE - FALSA ALARMA POR INCENDIO',
    'pre_hospitalario': '2. FICHA DE ATENCIÓN PRE-HOSPITALARIA / TRASLADO',
    'aph_traslado': '2. FICHA APH - TRASLADO DE EMERGENCIA',
    'aph_no_traslado': '2. FICHA APH - TRASLADO NO REALIZADO',
    'aph_interhospitalario': '2. FICHA APH - TRASLADO INTERHOSPITALARIO',
    'aph_sin_traslado': '2. FICHA APH - SIN TRASLADO',
    'incendio_estructura': '2. DETALLE DEL INCENDIO DE ESTRUCTURA',
    'incendio_apoyo': '2. DETALLE DEL APOYO POR INCENDIOS',
    'incendio_electrico': '2. DETALLE DEL INCENDIO DE EQUIPO ELÉCTRICO',
    'incendio_vehiculo': '2. DETALLE DEL INCENDIO DE VEHÍCULO',
    'incendio_desechos': '2. DETALLE DEL INCENDIO DE DESECHOS SÓLIDOS',
    'incendio_vegetacion': '2. DETALLE DEL INCENDIO DE VEGETACIÓN / FORESTAL',
    'incendio_arbol': '2. DETALLE DEL INCENDIO DE ÁRBOL',
    'rescate_colision_con_lesionado': '2. DETALLE DEL RESCATE - COLISIÓN CON LESIONADO',
    'rescate_colision_sin_lesionado': '2. DETALLE DEL RESCATE - COLISIÓN SIN LESIONADO',
    'rescate_volcamiento_con_lesionado': '2. DETALLE DEL RESCATE - VOLCAMIENTO CON LESIONADO',
    'rescate_volcamiento_sin_lesionado': '2. DETALLE DEL RESCATE - VOLCAMIENTO SIN LESIONADO',
    'rescate_ascensor': '2. DETALLE DEL RESCATE ESPECIALIZADO - ASCENSOR',
    'rescate_inmueble': '2. DETALLE DEL RESCATE ESPECIALIZADO - INMUEBLE',
    'rescate_tapiada': '2. DETALLE DEL RESCATE ESPECIALIZADO - TAPIADA',
    'rescate_golpeada': '2. DETALLE DEL RESCATE ESPECIALIZADO - GOLPEADA',
    'rescate_caida': '2. DETALLE DEL RESCATE DE PERSONA CAÍDA EN ALTURA',
    'rescate_cadaver': '2. DETALLE DEL RESCATE DE CADÁVER',
    'servicio_agua': '2. PARÁMETROS DEL ABASTECIMIENTO DE AGUA',
    'servicio_insectos': '2. PARÁMETROS DEL CONTROL Y REUBICACIÓN DE INSECTOS',
    'servicio_animal': '2. PARÁMETROS DEL CONTROL DE ANIMAL DOMÉSTICO',
    'servicio_achicamiento': '2. PARÁMETROS DEL ACHICAMIENTO POR AGUAS ESTANCADAS',
    'servicio_baldeo': '2. PARÁMETROS DEL BALDEO DE AGUA',
    'servicio_piscinas': '2. PARÁMETROS DEL RECORRIDO POR PISCINAS Y BALNEARIOS',
    'servicio_lluvias': '2. PARÁMETROS DEL RECORRIDO POR LLUVIAS',
    'inspeccion_insectos': '2. PARÁMETROS DE LA INSPECCIÓN DE INSECTOS',
    'apertura_puerta': '2. DATOS DEL INMUEBLE Y PROPIETARIO',
    'incendio_arbol_caido': '2. DETALLE DEL ÁRBOL CAÍDO',
    'siniestro_vial_con_lesionado': '2. DETALLE DEL SINIESTRO VIAL CON LESIONADO',
    'siniestro_vial_sin_lesionado': '2. DETALLE DEL SINIESTRO VIAL SIN LESIONADO',
    'busqueda_rescate': '2. DETALLE DE LA BÚSQUEDA Y RESCATE',
}

# Campos específicos por tipo de reporte: (Etiqueta del formulario, atributo del modelo, tipo de dato)
SECCIONES_ESPECIFICAS = {
    'matpel_glp': [
        ('Clasificación del Servicio', 'clasificacion_servicio', 'plain'),
        ('Nombre del Producto', 'nombre_producto', 'plain'),
        ('Número UN', 'un_numero', 'plain'),
        ('Tipo de Almacenamiento', 'tipo_almacenamiento', 'plain'),
        ('N° de Serie del Cilindro', 'serial_cilindro', 'plain'),
        ('Riesgo del Producto', 'riesgo_producto', 'plain'),
        ('Certificado Bomberil', 'certificado_bomberil', 'bool'),
        ('N° Certificado Bomberil', 'nro_certificado', 'plain'),
        ('Propietario / Responsable del Inmueble', 'propietario_nombre', 'plain'),
        ('C.I. / RIF del Propietario', 'propietario_rif_ci', 'plain'),
        ('Empresa / Distribuidor', 'empresa_distribuidora', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Hoja de Seguridad (HDS) en Sitio', 'hoja_seguridad', 'bool'),
        ('Extintor en el Sitio', 'extintor', 'bool'),
        ('Equipo para Control de Derrames', 'equipo_derrame', 'bool'),
    ],
    'matpel_combustible': [
        ('Tipo de Combustible', 'tipo_combustible', 'plain'),
        ('Tipo de Almacenamiento', 'tipo_almacenamiento', 'plain'),
        ('Código ONU (UN)', 'un_numero', 'plain'),
        ('Capacidad del Tanque (Lts.)', 'capacidad_tanque_litros', 'plain'),
        ('Cantidad Estimada de Derrame', 'cantidad_estimada_derrame', 'plain'),
        ('Riesgo del Producto', 'riesgo_producto', 'plain'),
        ('Tipo de Estructura', 'tipo_estructura', 'plain'),
        ('Propietario / Responsable', 'propietario_nombre', 'plain'),
        ('C.I. / RIF Propietario', 'propietario_rif_ci', 'plain'),
        ('Teléfono Propietario', 'propietario_telefono', 'plain'),
        ('Empresa Distribuidora', 'empresa_distribuidora', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados', 'plain'),
        ('Mitigación Efectuada', 'mitigacion_efectuada', 'plain'),
    ],
    'matpel_quimico': [
        ('Nombre de la Sustancia', 'nombre_sustancia', 'plain'),
        ('Número UN', 'un_numero', 'plain'),
        ('Riesgos Específicos del Producto', 'riesgos_especificos', 'plain'),
        ('Materiales Absorbentes Utilizados', 'materiales_absorbentes_usados', 'plain'),
        ('Materiales Neutralizantes Utilizados', 'materiales_neutralizantes_usados', 'plain'),
        ('Acciones de Mitigación', 'acciones_mitigacion', 'plain'),
        ('Origen del Derrame', 'origen_derrame', 'plain'),
        ('Tipo de Estructura', 'tipo_estructura', 'plain'),
        ('Propietario / Responsable', 'propietario_nombre', 'plain'),
        ('C.I. / RIF Propietario', 'propietario_rif_ci', 'plain'),
        ('Teléfono Propietario', 'propietario_telefono', 'plain'),
        ('Empresa Distribuidora', 'empresa_distribuidora', 'plain'),
        ('Marca del Vehículo', 'vehiculo_marca', 'plain'),
        ('Modelo del Vehículo', 'vehiculo_modelo', 'plain'),
        ('Placa del Vehículo', 'vehiculo_placa', 'plain'),
        ('Color del Vehículo', 'vehiculo_color', 'plain'),
    ],
    'matpel_otros': [
        ('Clasificación del Servicio', 'clasificacion_servicio', 'plain'),
        ('Nombre del Producto', 'nombre_producto', 'plain'),
        ('Número UN', 'un_numero', 'plain'),
        ('Tipo de Almacenamiento', 'tipo_almacenamiento', 'plain'),
        ('N° de Serie del Cilindro', 'serial_cilindro', 'plain'),
        ('Riesgo del Producto', 'riesgo_producto', 'plain'),
        ('Certificado Bomberil', 'certificado_bomberil', 'bool'),
        ('N° Certificado Bomberil', 'nro_certificado', 'plain'),
        ('Propietario / Responsable del Inmueble', 'propietario_nombre', 'plain'),
        ('C.I. / RIF del Propietario', 'propietario_rif_ci', 'plain'),
        ('Empresa / Distribuidor', 'empresa_distribuidora', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Hoja de Seguridad (HDS) en Sitio', 'hoja_seguridad', 'bool'),
        ('Extintor en el Sitio', 'extintor', 'bool'),
        ('Equipo para Control de Derrames', 'equipo_derrame', 'bool'),
    ],
    'falsa_alarma': [
        ('Tipo de Alarma', 'tipo_alarma', 'alarma'),
    ],

    'pre_hospitalario': [
        ('Nombre del Paciente', 'paciente_nombre', 'plain'),
        ('Cédula del Paciente', 'paciente_cedula', 'plain'),
        ('Edad', 'paciente_edad', 'plain'),
        ('Género', 'paciente_genero', 'plain'),
        ('Signos Vitales - Tensión Arterial', 'signos_vitales_tension', 'plain'),
        ('Signos Vitales - Pulso', 'signos_vitales_pulso', 'plain'),
        ('Signos Vitales - Frecuencia Respiratoria', 'signos_vitales_fr', 'plain'),
        ('Condición / Diagnóstico Clínico', 'condicion_paciente', 'plain'),
        ('Centro de Traslado (Destino)', 'centro_traslado', 'plain'),
        ('Material Médico Utilizado', 'material_medico_utilizado', 'plain'),
        ('Recomendaciones', 'recomendaciones', 'plain'),
    ],
    'servicio_agua': [
        ('Clasificación del Servicio', 'clasificacion_servicio', 'plain'),
        ('Litros Suministrados (Lts.)', 'litros_distribuidos', 'plain'),
        ('Beneficiarios Estimados', 'beneficiarios_estimados', 'plain'),
    ],
    'servicio_insectos': [
        ('Tipo de Insecto', 'tipo_insecto', 'plain'),
        ('Clasificación de Riesgo', 'clasificacion_riesgo', 'plain'),
        ('Condición Actual y Ubicación', 'condicion_actual', 'plain'),
        ('Método de Control', 'metodo_control', 'plain'),
        ('Materiales Utilizados', 'materiales_utilizados', 'plain'),
        ('Recomendaciones', 'recomendaciones', 'plain'),
    ],
    'servicio_animal': [
        ('Tipo de Animal', 'tipo_animal', 'plain'),
        ('Raza / Descripción', 'raza_descripcion', 'plain'),
        ('Condición del Animal', 'condicion_animal', 'plain'),
        ('Destino del Animal', 'destino_animal', 'plain'),
        ('Recomendaciones Técnicas', 'recomendaciones_tecnicas', 'plain'),
    ],
    'servicio_achicamiento': [
        ('Causa de la Inundación', 'causa_inundacion', 'plain'),
        ('Condición del Inmueble', 'condicion_inmueble', 'plain'),
        ('Bombas / Equipos Utilizados', 'bombas_usadas', 'plain'),
        ('Tiempo de Operación', 'tiempo_operacion', 'plain'),
        ('Nivel de Agua Inicial', 'nivel_agua_inicial', 'plain'),
        ('Nivel de Agua Final', 'nivel_agua_final', 'plain'),
        ('Observaciones / Inspección Técnica', 'inspeccion_tecnica_observaciones', 'plain'),
    ],
    'servicio_baldeo': [
        ('Motivo del Baldeo', 'motivo_baldeo', 'plain'),
        ('Área / Vía Afectada', 'area_afectada', 'plain'),
        ('Limpieza de Vías Efectuada', 'limpieza_vias_efectuada', 'bool'),
        ('Litros de Agua Utilizados (Lts.)', 'litros_agua_utilizados', 'plain'),
        ('Observaciones del Baldeo', 'observaciones_baldeo', 'plain'),
    ],
    'servicio_piscinas': [
        ('Clasificación del Servicio', 'clasificacion_servicio', 'plain'),
        ('Litros Suministrados (Lts.)', 'litros_distribuidos', 'plain'),
        ('Beneficiarios Estimados', 'beneficiarios_estimados', 'plain'),
    ],
    'servicio_lluvias': [
        ('Clasificación del Servicio', 'clasificacion_servicio', 'plain'),
        ('Litros Suministrados (Lts.)', 'litros_distribuidos', 'plain'),
        ('Beneficiarios Estimados', 'beneficiarios_estimados', 'plain'),
    ],
    'inspeccion_insectos': [
        ('Tipo de Insecto', 'tipo_insecto', 'plain'),
        ('Clasificación de Riesgo', 'clasificacion_riesgo', 'plain'),
        ('Condición Actual y Ubicación', 'condicion_actual', 'plain'),
        ('Materiales Utilizados', 'materiales_utilizados', 'plain'),
        ('Recomendaciones', 'recomendaciones', 'plain'),
    ],
    'apertura_puerta': [
        ('Propietario - Nombre', 'propietario_nombre', 'plain'),
        ('Propietario - C.I.', 'propietario_cedula', 'plain'),
        ('Propietario - Teléfono', 'propietario_telefono', 'plain'),
        ('Dirección del Inmueble', 'inmueble_direccion', 'plain'),
    ],
    # --- APH TRASLADO ---
    'aph_traslado': [
        ('Causa del Traslado', 'causa_traslado', 'plain'),
        ('Recomendaciones Especiales', 'recomendaciones', 'plain'),
        ('Presión Arterial', 'signos_vitales_pa', 'plain'),
        ('Frecuencia Cardíaca', 'signos_vitales_fc', 'plain'),
        ('Frecuencia Respiratoria', 'signos_vitales_fr', 'plain'),
        ('Temperatura', 'signos_vitales_temperatura', 'plain'),
        ('Glasgow - Apertura Ocular', 'glasgow_apertura_ocular', 'plain'),
        ('Glasgow - Respuesta Verbal', 'glasgow_respuesta_verbal', 'plain'),
        ('Glasgow - Respuesta Motora', 'glasgow_respuesta_motora', 'plain'),
        ('Glasgow Total', 'glasgow_total', 'plain'),
        ('Regla 9 - Cabeza', 'regla_9_cabeza', 'plain'),
        ('Regla 9 - Tórax', 'regla_9_torax', 'plain'),
        ('Regla 9 - Abdomen', 'regla_9_abdomen', 'plain'),
        ('Regla 9 - M. Sup. Derecho', 'regla_9_miembro_superior_d', 'plain'),
        ('Regla 9 - M. Sup. Izquierdo', 'regla_9_miembro_superior_i', 'plain'),
        ('Regla 9 - M. Inf. Derecho', 'regla_9_miembro_inferior_d', 'plain'),
        ('Regla 9 - M. Inf. Izquierdo', 'regla_9_miembro_inferior_i', 'plain'),
        ('Regla 9 - Total', 'regla_9_total', 'plain'),
        ('Procedimientos Paraclínicos', 'procedimiento_paraclinico', 'plain'),
        ('Medicinas Utilizadas', 'medicinas_usadas', 'plain'),
        ('Material Médico', 'material_medico_usado', 'plain'),
        ('Centro Hospitalario', 'centro_hospitalario', 'plain'),
        ('Médico que Recibe', 'medico_recibe', 'plain'),
        ('Cédula Médico', 'medico_cedula', 'plain'),
        ('MSDS', 'medico_msds', 'plain'),
        ('Firma Médico', 'medico_firma', 'bool'),
        ('Rechazo - Nombre', 'rechazo_nombre', 'plain'),
        ('Rechazo - Cédula', 'rechazo_cedula', 'plain'),
        ('Rechazo - Firma', 'rechazo_firma', 'bool'),
    ],
    # --- APH NO TRASLADO ---
    'aph_no_traslado': [
        ('Causa de la Atención', 'causa_traslado', 'plain'),
        ('Recomendaciones Especiales', 'recomendaciones', 'plain'),
        ('Presión Arterial', 'signos_vitales_pa', 'plain'),
        ('Frecuencia Cardíaca', 'signos_vitales_fc', 'plain'),
        ('Frecuencia Respiratoria', 'signos_vitales_fr', 'plain'),
        ('Temperatura', 'signos_vitales_temperatura', 'plain'),
        ('Regla 9 - Total', 'regla_9_total', 'plain'),
        ('Procedimientos Paraclínicos', 'procedimiento_paraclinico', 'plain'),
        ('Medicinas Utilizadas', 'medicinas_usadas', 'plain'),
        ('Material Médico', 'material_medico_usado', 'plain'),
        ('Motivo del No Traslado', 'motivo_no_traslado', 'plain'),
        ('Indicaciones Dejadas', 'indicaciones_dejadas', 'plain'),
        ('Firma del Paciente', 'paciente_firma', 'bool'),
        ('Rechazo - Nombre', 'rechazo_nombre', 'plain'),
        ('Rechazo - Cédula', 'rechazo_cedula', 'plain'),
    ],
    # --- APH INTERHOSPITALARIO ---
    'aph_interhospitalario': [
        ('Causa del Traslado', 'causa_traslado', 'plain'),
        ('Recomendaciones Especiales', 'recomendaciones', 'plain'),
        ('Presión Arterial', 'signos_vitales_pa', 'plain'),
        ('Frecuencia Cardíaca', 'signos_vitales_fc', 'plain'),
        ('Frecuencia Respiratoria', 'signos_vitales_fr', 'plain'),
        ('Temperatura', 'signos_vitales_temperatura', 'plain'),
        ('Glasgow Total', 'glasgow_total', 'plain'),
        ('Regla 9 - Total', 'regla_9_total', 'plain'),
        ('Procedimientos Paraclínicos', 'procedimiento_paraclinico', 'plain'),
        ('Medicinas Utilizadas', 'medicinas_usadas', 'plain'),
        ('Material Médico', 'material_medico_usado', 'plain'),
        ('Centro de Origen', 'centro_origen', 'plain'),
        ('Médico de Origen', 'medico_origen', 'plain'),
        ('Centro de Destino', 'centro_destino', 'plain'),
        ('Médico que Recibe', 'medico_recibe', 'plain'),
        ('Rechazo - Nombre', 'rechazo_nombre', 'plain'),
        ('Rechazo - Cédula', 'rechazo_cedula', 'plain'),
    ],
    # --- APH SIN TRASLADO ---
    'aph_sin_traslado': [
        ('Causa de la Atención', 'causa_traslado', 'plain'),
        ('Recomendaciones Especiales', 'recomendaciones', 'plain'),
        ('Presión Arterial', 'signos_vitales_pa', 'plain'),
        ('Frecuencia Cardíaca', 'signos_vitales_fc', 'plain'),
        ('Frecuencia Respiratoria', 'signos_vitales_fr', 'plain'),
        ('Temperatura', 'signos_vitales_temperatura', 'plain'),
        ('Glasgow Total', 'glasgow_total', 'plain'),
        ('Regla 9 - Total', 'regla_9_total', 'plain'),
        ('Procedimientos Paraclínicos', 'procedimiento_paraclinico', 'plain'),
        ('Medicinas Utilizadas', 'medicinas_usadas', 'plain'),
        ('Material Médico', 'material_medico_usado', 'plain'),
        ('Conducta Adoptada', 'conducta_adoptada', 'plain'),
        ('Indicaciones Dejadas', 'indicaciones_dejadas', 'plain'),
        ('Rechazo - Nombre', 'rechazo_nombre', 'plain'),
        ('Rechazo - Cédula', 'rechazo_cedula', 'plain'),
    ],
    # --- INCENDIO (campos segun subtipo; los vacios se omiten en el DTO) ---
    'incendio_estructura': [
        ('Clase de Incendio', 'clase_incendio', 'clase'),
        ('Tipo de Estructura', 'tipo_estructura', 'plain'),
        ('Lugar de Desarrollo', 'lugar_desarrollo', 'plain'),
        ('Presunto Punto de Origen', 'presunto_punto_origen', 'plain'),
        ('Salida Primera Maquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Maquina', 'salida_segunda_maquina', 'hora'),
        ('Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Salida Unidad Adicional', 'salida_unidad_adicional', 'hora'),
        ('Nombre Unidad Adicional', 'salida_unidad_adicional_nombre', 'plain'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('% Perdida Fuego', 'porcentaje_perdida_fuego', 'plain'),
        ('% Perdida Humo', 'porcentaje_perdida_humo', 'plain'),
        ('% Perdida Total', 'porcentaje_perdida_total', 'plain'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Hubo Propagacion', 'hubo_propagacion', 'bool'),
        ('Propagacion - Donde', 'propagacion_donde', 'plain', 'propagacion'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Poseia Equipos', 'poseia_equipos', 'bool'),
        ('Fueron Usados', 'fue_usado', 'bool', 'equipos_poseia'),
        ('Usados Por', 'por_quien_uso', 'plain', 'equipos_usados'),
        ('C.I. Usado Por', 'por_quien_ci', 'plain', 'equipos_usados'),
        ('Tipo de Equipo Usado', 'tipo_equipo_contra_incendio', 'plain', 'equipos_usados'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
        ('Inmueble - Descripcion', 'inmueble_descripcion', 'plain'),
        ('Inmueble - Propietario', 'inmueble_propietario_nombre', 'plain'),
        ('Inmueble - C.I. / RIF', 'inmueble_propietario_cedula', 'plain'),
        ('Inmueble - Telefono', 'inmueble_propietario_telefono', 'plain'),
        ('Inmueble - Valor', 'inmueble_valor', 'money'),
        ('Inmueble - Perdidas', 'inmueble_perdidas', 'money'),
        ('Inmueble - Aseguradora', 'inmueble_aseguradora', 'plain'),
        ('Mueble - Propietario', 'mueble_propietario', 'plain'),
        ('Mueble - C.I. / RIF', 'mueble_propietario_ci', 'plain'),
        ('Mueble - Valor', 'mueble_valor', 'money'),
        ('Mueble - Perdidas', 'mueble_perdidas', 'money'),
        ('Mueble - Aseguradora', 'mueble_aseguradora', 'plain'),
        ('Mueble - Condicion', 'mueble_condicion', 'plain'),
        ('Lugar a cargo de', 'lugar_a_cargo', 'plain'),
    ],
    'incendio_apoyo': [
        ('Tipo de Incendio Apoyado', 'tipo_apoyo', 'apoyo'),
        ('Clase de Incendio', 'clase_incendio', 'clase'),
        ('Tipo de Estructura', 'tipo_estructura', 'plain'),
        ('Tipo de Incendio', 'tipo_incendio', 'plain'),
        ('Lugar de Desarrollo', 'lugar_desarrollo', 'plain'),
        ('Presunto Punto de Origen', 'presunto_punto_origen', 'plain'),
        ('Salida Primera Maquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Maquina', 'salida_segunda_maquina', 'hora'),
        ('Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Salida Unidad Adicional', 'salida_unidad_adicional', 'hora'),
        ('Nombre Unidad Adicional', 'salida_unidad_adicional_nombre', 'plain'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('% Perdida Fuego', 'porcentaje_perdida_fuego', 'plain'),
        ('% Perdida Humo', 'porcentaje_perdida_humo', 'plain'),
        ('% Perdida Total', 'porcentaje_perdida_total', 'plain'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Hubo Propagacion', 'hubo_propagacion', 'bool'),
        ('Propagacion - Donde', 'propagacion_donde', 'plain', 'propagacion'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Poseia Equipos', 'poseia_equipos', 'bool'),
        ('Fueron Usados', 'fue_usado', 'bool', 'equipos_poseia'),
        ('Usados Por', 'por_quien_uso', 'plain', 'equipos_usados'),
        ('C.I. Usado Por', 'por_quien_ci', 'plain', 'equipos_usados'),
        ('Tipo de Equipo Usado', 'tipo_equipo_contra_incendio', 'plain', 'equipos_usados'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
        ('Inmueble - Descripcion', 'inmueble_descripcion', 'plain'),
        ('Inmueble - Propietario', 'inmueble_propietario_nombre', 'plain'),
        ('Inmueble - C.I. / RIF', 'inmueble_propietario_cedula', 'plain'),
        ('Inmueble - Telefono', 'inmueble_propietario_telefono', 'plain'),
        ('Inmueble - Valor', 'inmueble_valor', 'money'),
        ('Inmueble - Perdidas', 'inmueble_perdidas', 'money'),
        ('Inmueble - Aseguradora', 'inmueble_aseguradora', 'plain'),
        ('Mueble - Propietario', 'mueble_propietario', 'plain'),
        ('Mueble - C.I. / RIF', 'mueble_propietario_ci', 'plain'),
        ('Mueble - Valor', 'mueble_valor', 'money'),
        ('Mueble - Perdidas', 'mueble_perdidas', 'money'),
        ('Mueble - Aseguradora', 'mueble_aseguradora', 'plain'),
        ('Mueble - Condicion', 'mueble_condicion', 'plain'),
        ('Lugar a cargo de', 'lugar_a_cargo', 'plain'),
        ('Sistema Electrico - Tipo', 'sistema_electrico_tipo', 'plain'),
        ('Sistema Electrico - Capacidad', 'sistema_electrico_capacidad', 'plain'),
        ('Sistema Electrico - Uso', 'sistema_electrico_uso', 'plain'),
        ('Sistema Electrico - Serial', 'sistema_electrico_serial', 'plain'),
        ('Sistema Electrico - Propiedad', 'sistema_electrico_propiedad', 'plain'),
        ('Sistema Electrico - RIF', 'sistema_electrico_rif', 'plain'),
        ('Desperdicio - Materia Prima', 'desperdicio_materia', 'plain'),
        ('Desperdicio - Cantidad', 'desperdicio_cantidad', 'plain'),
        ('Desperdicio - Recuperable', 'desperdicio_recuperable', 'plain'),
        ('Arbol - Edad', 'arbol_edad', 'plain'),
        ('Arbol - Longitud', 'arbol_longitud', 'plain'),
        ('Arbol - Circunferencia', 'arbol_circunferencia', 'plain'),
        ('Arbol - Especie', 'arbol_especie', 'plain'),
        ('Tipo de Terreno', 'tipo_terreno', 'plain'),
        ('Tipo de Vegetacion', 'tipo_vegetacion', 'plain'),
        ('Extension Terreno', 'extension_terreno', 'plain'),
        ('Extension Afectada', 'extension_terreno_afectada', 'plain'),
        ('Coordenadas', 'coordenadas', 'plain'),
    ],
    'incendio_electrico': [
        ('Equipo Contra Incendio', 'tipo_equipo_contra_incendio', 'plain'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
        ('Sistema Electrico - Tipo', 'sistema_electrico_tipo', 'plain'),
        ('Sistema Electrico - Capacidad', 'sistema_electrico_capacidad', 'plain'),
        ('Sistema Electrico - Uso', 'sistema_electrico_uso', 'plain'),
        ('Sistema Electrico - Serial', 'sistema_electrico_serial', 'plain'),
        ('Sistema Electrico - Propiedad', 'sistema_electrico_propiedad', 'plain'),
        ('Sistema Electrico - RIF', 'sistema_electrico_rif', 'plain'),
    ],
    'incendio_vehiculo': [
        ('Clase de Incendio', 'clase_incendio', 'clase'),
        ('Lugar de Desarrollo', 'lugar_desarrollo', 'plain'),
        ('Presunto Punto de Origen', 'presunto_punto_origen', 'plain'),
        ('Salida Primera Maquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Maquina', 'salida_segunda_maquina', 'hora'),
        ('Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Salida Unidad Adicional', 'salida_unidad_adicional', 'hora'),
        ('Nombre Unidad Adicional', 'salida_unidad_adicional_nombre', 'plain'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('% Perdida Fuego', 'porcentaje_perdida_fuego', 'plain'),
        ('% Perdida Humo', 'porcentaje_perdida_humo', 'plain'),
        ('% Perdida Total', 'porcentaje_perdida_total', 'plain'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Hubo Propagacion', 'hubo_propagacion', 'bool'),
        ('Propagacion - Donde', 'propagacion_donde', 'plain', 'propagacion'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Poseia Equipos', 'poseia_equipos', 'bool'),
        ('Fueron Usados', 'fue_usado', 'bool', 'equipos_poseia'),
        ('Usados Por', 'por_quien_uso', 'plain', 'equipos_usados'),
        ('C.I. Usado Por', 'por_quien_ci', 'plain', 'equipos_usados'),
        ('Tipo de Equipo Usado', 'tipo_equipo_contra_incendio', 'plain', 'equipos_usados'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
    ],
    'incendio_desechos': [
        ('Equipo Contra Incendio', 'tipo_equipo_contra_incendio', 'plain'),
        ('Salida Primera Maquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Maquina', 'salida_segunda_maquina', 'hora'),
        ('Salida Unidad Adicional', 'salida_unidad_adicional', 'hora'),
        ('Nombre Unidad Adicional', 'salida_unidad_adicional_nombre', 'plain'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('% Perdida Fuego', 'porcentaje_perdida_fuego', 'plain'),
        ('% Perdida Humo', 'porcentaje_perdida_humo', 'plain'),
        ('% Perdida Total', 'porcentaje_perdida_total', 'plain'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
        ('Desperdicio - Materia Prima', 'desperdicio_materia', 'plain'),
        ('Desperdicio - Cantidad', 'desperdicio_cantidad', 'plain'),
        ('Desperdicio - Recuperable', 'desperdicio_recuperable', 'plain'),
    ],
    'incendio_vegetacion': [
        ('Tipo de Incendio', 'tipo_incendio', 'plain'),
        ('Equipo Contra Incendio', 'tipo_equipo_contra_incendio', 'plain'),
        ('Salida Primera Maquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Maquina', 'salida_segunda_maquina', 'hora'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
        ('Tipo de Terreno', 'tipo_terreno', 'plain'),
        ('Tipo de Vegetacion', 'tipo_vegetacion', 'plain'),
        ('Extension Terreno', 'extension_terreno', 'plain'),
        ('Extension Afectada', 'extension_terreno_afectada', 'plain'),
        ('Coordenadas', 'coordenadas', 'plain'),
    ],
    'incendio_arbol': [
        ('Salida Primera Maquina', 'salida_primera_maquina', 'hora'),
        ('Arbol - Edad', 'arbol_edad', 'plain'),
        ('Arbol - Longitud', 'arbol_longitud', 'plain'),
        ('Arbol - Circunferencia', 'arbol_circunferencia', 'plain'),
        ('Arbol - Especie', 'arbol_especie', 'plain'),
        ('Equipo Contra Incendio', 'tipo_equipo_contra_incendio', 'plain'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
    ],
    'incendio_arbol_caido': [
        ('Objeto Afectado', 'arbol_afecto', 'afecto'),
        ('Tipo de Estructura', 'tipo_estructura', 'plain'),
        ('Lugar de Desarrollo', 'lugar_desarrollo', 'plain'),
        ('Presunto Punto de Origen', 'presunto_punto_origen', 'plain'),
        ('Hora de Control', 'hora_control', 'hora'),
        ('Hora Extincion Total', 'hora_extincion_total', 'hora'),
        ('% Perdida Total', 'porcentaje_perdida_total', 'plain'),
        ('Litros de Agua', 'litros_agua_utilizados', 'plain'),
        ('Hubo Propagacion', 'hubo_propagacion', 'bool'),
        ('Propagacion - Donde', 'propagacion_donde', 'plain', 'propagacion'),
        ('Metodos de Extincion', 'metodos_extincion', 'plain'),
        ('Tecnicas de Extincion', 'tecnicas_extincion', 'plain'),
        ('Poseia Equipos', 'poseia_equipos', 'bool'),
        ('Fueron Usados', 'fue_usado', 'bool', 'equipos_poseia'),
        ('Usados Por', 'por_quien_uso', 'plain', 'equipos_usados'),
        ('C.I. Usado Por', 'por_quien_ci', 'plain', 'equipos_usados'),
        ('Tipo de Equipo Usado', 'tipo_equipo_contra_incendio', 'plain', 'equipos_usados'),
        ('Evaluacion Preliminar', 'evaluacion_preliminar', 'plain'),
        ('Inmueble - Descripcion', 'inmueble_descripcion', 'plain'),
        ('Inmueble - Propietario', 'inmueble_propietario_nombre', 'plain'),
        ('Inmueble - C.I. / RIF', 'inmueble_propietario_cedula', 'plain'),
        ('Inmueble - Telefono', 'inmueble_propietario_telefono', 'plain'),
        ('Inmueble - Valor', 'inmueble_valor', 'money'),
        ('Inmueble - Perdidas', 'inmueble_perdidas', 'money'),
        ('Inmueble - Aseguradora', 'inmueble_aseguradora', 'plain'),
        ('Mueble - Propietario', 'mueble_propietario', 'plain'),
        ('Mueble - C.I. / RIF', 'mueble_propietario_ci', 'plain'),
        ('Mueble - Valor', 'mueble_valor', 'money'),
        ('Mueble - Perdidas', 'mueble_perdidas', 'money'),
        ('Mueble - Aseguradora', 'mueble_aseguradora', 'plain'),
        ('Mueble - Condicion', 'mueble_condicion', 'plain'),
        ('Lugar a cargo de', 'lugar_a_cargo', 'plain'),
    ],

# --- RESCATE COLISIÓN / VOLCAMIENTO ---
    'rescate_colision_con_lesionado': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Observaciones Custodio', 'observaciones_custodio', 'plain'),
        ('Responsable Vehículo', 'vehiculo_cargo_nombre', 'plain'),
        ('C.I. Responsable', 'vehiculo_cargo_cedula', 'plain'),
        ('Teléfono Responsable', 'vehiculo_cargo_telefono', 'plain'),
    ],
    'rescate_colision_sin_lesionado': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Observaciones Custodio', 'observaciones_custodio', 'plain'),
        ('Responsable Vehículo', 'vehiculo_cargo_nombre', 'plain'),
        ('C.I. Responsable', 'vehiculo_cargo_cedula', 'plain'),
        ('Teléfono Responsable', 'vehiculo_cargo_telefono', 'plain'),
    ],
    'rescate_volcamiento_con_lesionado': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Observaciones Custodio', 'observaciones_custodio', 'plain'),
        ('Responsable Vehículo', 'vehiculo_cargo_nombre', 'plain'),
        ('C.I. Responsable', 'vehiculo_cargo_cedula', 'plain'),
        ('Teléfono Responsable', 'vehiculo_cargo_telefono', 'plain'),
    ],
    'rescate_volcamiento_sin_lesionado': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Observaciones Custodio', 'observaciones_custodio', 'plain'),
        ('Responsable Vehículo', 'vehiculo_cargo_nombre', 'plain'),
        ('C.I. Responsable', 'vehiculo_cargo_cedula', 'plain'),
        ('Teléfono Responsable', 'vehiculo_cargo_telefono', 'plain'),
    ],
    # --- RESCATE ESPECIALIZADO ---
    'rescate_ascensor': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Tipo de Servicio', 'tipo_servicio', 'plain'),
        ('Hora Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Material Utilizado', 'despliegue_material_usado', 'plain'),
    ],
    'rescate_inmueble': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Tipo de Servicio', 'tipo_servicio', 'plain'),
        ('Hora Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Material Utilizado', 'despliegue_material_usado', 'plain'),
    ],
    'rescate_tapiada': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Tipo de Servicio', 'tipo_servicio', 'plain'),
        ('Hora Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Material Utilizado', 'despliegue_material_usado', 'plain'),
        ('Motivo de la Tapiada', 'motivo_tapiada', 'plain'),
    ],
    'rescate_golpeada': [
        ('Subtipo', 'subtipo_rescate', 'plain'),
        ('Tipo de Servicio', 'tipo_servicio', 'plain'),
        ('Hora Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Material Utilizado', 'despliegue_material_usado', 'plain'),
        ('Motivo de la Golpeada', 'motivo_golpeada', 'plain'),
        ('Golpeada por Vehículo', 'golpeada_por_vehiculo', 'bool'),
        ('Vehículo - Marca', 'golpeada_vehiculo_marca', 'plain'),
        ('Vehículo - Modelo', 'golpeada_vehiculo_modelo', 'plain'),
        ('Vehículo - Placa', 'golpeada_vehiculo_placa', 'plain'),
        ('Vehículo - Color', 'golpeada_vehiculo_color', 'plain'),
        ('Conductor', 'golpeada_conductor_nombre', 'plain'),
        ('C.I. Conductor', 'golpeada_conductor_ci', 'plain'),
        ('Teléfono Conductor', 'golpeada_conductor_telefono', 'plain'),
    ],
    # Caída en altura: se muestran los datos del lesionado (personas afectadas)
    # y el tipo de terreno donde ocurrió el rescate, en lugar del despliegue.
    'rescate_caida': [
        ('Tipo de Rescate', 'subtipo_rescate', 'plain'),
        ('Tipo de Terreno', 'tipo_terreno', 'plain'),
        ('Salida Primera Máquina', 'salida_primera_maquina', 'hora'),
        ('Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Material Utilizado', 'despliegue_material_usado', 'plain'),
    ],
    # Cadáver: datos del fallecido y ubicación del hallazgo.
    'rescate_cadaver': [
        ('Tipo de Rescate', 'subtipo_rescate', 'plain'),
        ('Nombre del Fallecido', 'cadaver_nombre', 'plain'),
        ('C.I. / Pasaporte', 'cadaver_cedula', 'plain'),
        ('Edad', 'cadaver_edad', 'plain'),
        ('Sexo', 'cadaver_sexo', 'plain'),
        ('Ubicación donde se encontró', 'cadaver_ubicacion', 'plain'),
        ('Material Utilizado', 'despliegue_material_usado', 'plain'),
    ],
    'siniestro_vial_con_lesionado': [
        ('Tipo de Siniestro', 'tipo_siniestro', 'plain'),
        ('Salida Primera Máquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Máquina', 'salida_segunda_maquina', 'hora'),
        ('Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Salida Unidad Adicional', 'salida_unidad_adicional', 'hora'),
        ('Nombre Unidad Adicional', 'salida_unidad_adicional_nombre', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Observaciones Custodio', 'observaciones_custodio', 'plain'),
        ('Responsable Vehículo', 'vehiculo_cargo_nombre', 'plain'),
        ('C.I. Responsable', 'vehiculo_cargo_cedula', 'plain'),
        ('Teléfono Responsable', 'vehiculo_cargo_telefono', 'plain'),
    ],
    'siniestro_vial_sin_lesionado': [
        ('Tipo de Siniestro', 'tipo_siniestro', 'plain'),
        ('Salida Primera Máquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Máquina', 'salida_segunda_maquina', 'hora'),
        ('Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Salida Unidad Adicional', 'salida_unidad_adicional', 'hora'),
        ('Nombre Unidad Adicional', 'salida_unidad_adicional_nombre', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados_json', 'plain'),
        ('Observaciones Custodio', 'observaciones_custodio', 'plain'),
        ('Responsable Vehículo', 'vehiculo_cargo_nombre', 'plain'),
        ('C.I. Responsable', 'vehiculo_cargo_cedula', 'plain'),
        ('Teléfono Responsable', 'vehiculo_cargo_telefono', 'plain'),
    ],
    'busqueda_rescate': [
        ('Tipo de Zona', 'tipo_zona', 'plain'),
        ('Salida Primera Máquina', 'salida_primera_maquina', 'hora'),
        ('Salida Segunda Máquina', 'salida_segunda_maquina', 'hora'),
        ('Salida Ambulancia', 'salida_ambulancia', 'hora'),
        ('Salida Unidad Adicional', 'salida_unidad_adicional', 'hora'),
        ('Nombre Unidad Adicional', 'salida_unidad_adicional_nombre', 'plain'),
        ('Material Utilizado', 'material_usado', 'plain'),
    ],
}

# Campo del modelo que describe el material/equipos usados en la actuación, según el tipo
MATERIAL_ATTR = {
    'matpel_glp': None,
    'matpel_combustible': 'mitigacion_efectuada',
    'matpel_quimico': 'materiales_absorbentes_usados',
    'matpel_otros': None,
    'falsa_alarma': None,
    'pre_hospitalario': 'material_medico_utilizado',
    'aph_traslado': 'material_medico_usado',
    'aph_no_traslado': 'material_medico_usado',
    'aph_interhospitalario': 'material_medico_usado',
    'aph_sin_traslado': 'material_medico_usado',
    'incendio_estructura': None,
    'incendio_apoyo': None,
    'incendio_electrico': None,
    'incendio_vehiculo': None,
    'incendio_desechos': None,
    'incendio_vegetacion': None,
    'incendio_arbol': None,
    'rescate_colision_con_lesionado': None,
    'rescate_colision_sin_lesionado': None,
    'rescate_volcamiento_con_lesionado': None,
    'rescate_volcamiento_sin_lesionado': None,
    'siniestro_vial_con_lesionado': 'observaciones_custodio',
    'siniestro_vial_sin_lesionado': 'observaciones_custodio',
    'busqueda_rescate': 'material_usado',
    'rescate_ascensor': 'despliegue_material_usado',
    'rescate_inmueble': 'despliegue_material_usado',
    'rescate_tapiada': 'despliegue_material_usado',
    'rescate_golpeada': 'despliegue_material_usado',
    'rescate_caida': None,
    'rescate_cadaver': None,
    'servicio_agua': 'material_usado',
    'servicio_insectos': 'materiales_utilizados',
    'inspeccion_insectos': 'materiales_utilizados',
    'servicio_piscinas': 'material_usado',
    'servicio_lluvias': 'material_usado',
    'apertura_puerta': None,
    'incendio_arbol_caido': None,
    'servicio_animal': None,
    'servicio_achicamiento': 'bombas_usadas',
    'servicio_baldeo': None,
}


def _formatear_valor(valor, tipo):
    """
    Normaliza el valor de un campo para mostrarlo en el PDF.
    Los booleanos se imprimen como SÍ/NO; los nulos como '—'.
    """
    if valor is None or valor == '':
        return '—'
    if tipo == 'bool':
        return 'SÍ' if valor else 'NO'
    if tipo == 'clase':
        return {'1': 'Primera clase', '2': 'Segunda clase', '3': 'Tercera clase'}.get(str(valor), str(valor))
    if tipo == 'hora':
        return _formatear_hora(valor, con_segundos=True)
    if tipo == 'money':
        try:
            return f'{float(valor):,.2f}'
        except (TypeError, ValueError):
            return str(valor)
    if tipo == 'apoyo':
        return {
            'estructura': 'Incendio de Estructura',
            'vehiculo': 'Incendio de Vehículo',
            'electrico': 'Incendio de Equipo Eléctrico',
            'desechos': 'Incendio de Desechos Sólidos',
            'vegetacion': 'Incendio de Vegetación / Forestal',
            'arbol': 'Incendio de Árbol',
        }.get(str(valor), str(valor))
    if tipo == 'afecto':
        return {
            'estructura': 'Inmueble / Estructura',
            'vehiculo': 'Vehículo',
        }.get(str(valor), str(valor))
    if tipo == 'alarma':
        return {
            'incendio_estructura': 'Incendio de Estructura',
            'incendio_vehiculo': 'Incendio de Vehículo',
        }.get(str(valor), str(valor))
    return str(valor)


def _formatear_fecha(fecha):
    return fecha.strftime('%d/%m/%Y') if fecha else '—'


def _formatear_hora(hora, con_segundos=False):
    if not hora:
        return '—'
    return hora.strftime('%H:%M:%S' if con_segundos else '%H:%M')


def _formatear_personal(persona):
    """
    Convierte un ReportePersonalActuante en un mini-DTO de firmas.
    Evita duplicar el rango si ya viene incluido en el nombre.
    """
    if persona is None:
        return None
    nombre = (persona.nombre_completo or '').strip()
    rango = (persona.rango or '').strip()
    if rango and nombre and not nombre.lower().startswith(rango.lower()):
        nombre = f'{rango} {nombre}'
    return {
        'nombre': nombre or '—',
        'cedula': persona.cedula or '—',
    }


def _nl2br_html(texto):
    """
    Escapa el texto y convierte saltos de línea en <br> para renderizarlo
    con |safe en la plantilla (compatible con xhtml2pdf y WeasyPrint).
    """
    if not texto:
        return '—'
    return texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')


@lru_cache(maxsize=1)
def obtener_logo_data_uri():
    """
    Lee el logotipo oficial desde app/static/imagen/logo-bomberos.png y lo
    devuelve como Data URI (data:image/png;base64,...) para incrustarlo
    directamente en el HTML del PDF.

    Ventajas de este enfoque frente a una URL:
      - No falla si el servidor web no puede resolver URLs absolutas.
      - No depende de autenticación ni de la carpeta /static en producción.
      - WeasyPrint y xhtml2pdf incrustan la imagen sin conexión a internet.

    La imagen se re-dimensiona (máx. 220px de ancho) para reducir el peso
    final del PDF. Si el archivo no existe, se devuelve '' y la plantilla
    muestra un recuadro de respaldo.
    """
    try:
        with open(RUTA_LOGO, 'rb') as f:
            data = f.read()
        try:
            from PIL import Image
            imagen = Image.open(io.BytesIO(data))
            if imagen.width > 220:
                alto = int(imagen.height * 220 / imagen.width)
                imagen = imagen.resize((220, alto), Image.LANCZOS)
            if imagen.mode not in ('RGB', 'RGBA'):
                imagen = imagen.convert('RGBA')
            buffer = io.BytesIO()
            imagen.save(buffer, format='PNG', optimize=True)
            data = buffer.getvalue()
        except Exception:
            pass
        return 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')
    except Exception:
        return ''


def serializar_reporte(reporte):
    """
    Convierte un Reporte (SQLAlchemy) en el DTO plano que consume la plantilla
    reporte_pdf.html.

    Estructura del DTO (JSON-friendly):
    {
      "logo":                "data:image/png;base64,...",
      "nro_control":         "GLP-2026-0001",
      "nombre_servicio":     "CONTROL DE ESCAPE DE GAS LICUADO...",
      "titulo_seccion_2":    "2. DETALLE TÉCNICO - ...",
      "fecha_incidente":     "17/08/2026",
      "fecha_emision":       "17/08/2026 14:30",
      "clase_aviso":         "Radial",
      "receptor_aviso":      "Cabo Pérez",
      "horas":               [{"etiqueta": "Hora de Aviso",  "valor": "08:30"}, ...],
      "solicitante_nombre":  "...", "solicitante_cedula": "...", "solicitante_telefono": "...",
      "direccion":           "...", "punto_referencia": "...",
      "especifico":          [{"etiqueta": "Número UN", "valor": "UN 1075"}, ...],
      "vehiculos":           [{"unidad","tipo","placa","conductor","km_salida","km_llegada","recorrido"}, ...],
      "material_bomberil":   "...",
      "total_efectivos":     4,
      "jefe_comision":       {"nombre","cedula"} | None,
      "conductor_unidad":    {"nombre","cedula"} | None,
      "elaborado_por":       {"nombre","cedula"} | None,
      "combatientes":        [{"nombre","cedula"}, ...],
      "otros_organismos":    [{"nombre","jefe","matricula","cantidad"}, ...],
      "observaciones":       "...",
      "estado":              "Enviado"
    }
    """
    tipo = reporte.tipo_especifico

    def _es_incendio(t):
        return bool(t) and t.startswith('incendio')

    especifico = []
    if _es_incendio(tipo):
        # Los campos condicionales/vacíos no se incluyen para no dejar
        # espacios en blanco en el PDF.
        tipo_sec = tipo
        if tipo == 'incendio_apoyo':
            tipo_sec = 'incendio_' + (reporte.tipo_apoyo or 'estructura')
        if tipo == 'incendio_apoyo':
            especifico.append({
                'etiqueta': 'Tipo de Incendio Apoyado',
                'valor': _formatear_valor(reporte.tipo_apoyo, 'apoyo'),
            })
        for fila in SECCIONES_ESPECIFICAS.get(tipo_sec, []):
            etiqueta, attr, tipo_dato = fila[0], fila[1], fila[2]
            cond = fila[3] if len(fila) > 3 else None
            if cond == 'propagacion' and not reporte.hubo_propagacion:
                continue
            if cond == 'equipos_poseia' and not reporte.poseia_equipos:
                continue
            if cond == 'equipos_usados' and not (reporte.poseia_equipos and reporte.fue_usado):
                continue
            if attr == 'tipo_apoyo':
                continue
            valor = getattr(reporte, attr, None)
            if attr in ('hubo_propagacion', 'poseia_equipos') and not valor:
                continue
            if valor is None or valor == '':
                continue
            especifico.append({
                'etiqueta': etiqueta,
                'valor': _formatear_valor(valor, tipo_dato),
            })
    else:
        for etiqueta, attr, tipo_dato in SECCIONES_ESPECIFICAS.get(tipo, []):
            especifico.append({
                'etiqueta': etiqueta,
                'valor': _formatear_valor(getattr(reporte, attr, None), tipo_dato),
            })

    vehiculos = []
    for va in reporte.vehiculos_actuantes:
        vehiculo = va.vehiculo
        km_salida = float(va.km_salida or 0)
        km_llegada = float(va.km_llegada or 0)
        vehiculos.append({
            'unidad': vehiculo.unidad if vehiculo else '—',
            'tipo': vehiculo.tipo if vehiculo else '—',
            'placa': vehiculo.placa if vehiculo else '—',
            'conductor': va.conductor_nombre or '—',
            'hora_salida': _formatear_hora(va.hora_salida, con_segundos=True),
            'km_salida': f'{km_salida:.2f}',
            'km_llegada': f'{km_llegada:.2f}',
            'recorrido': f'{km_llegada - km_salida:.2f}',
        })

    personal = list(reporte.personal_actuante)
    jefe = next((p for p in personal if p.rol_en_servicio == 'Jefe de Comisión'), None)
    conductor = next((p for p in personal if p.rol_en_servicio == 'Conductor Unidad'), None)
    elaborado = next((p for p in personal if 'Elaborado' in (p.rol_en_servicio or '')), None)
    combatientes = [_formatear_personal(p) for p in personal if p.rol_en_servicio == 'Combatiente']

    otros_organismos = [{
        'nombre': org.nombre_organismo,
        'jefe': org.jefe_unidad or '—',
        'matricula': org.matricula_unidad or '—',
        'cantidad': org.cantidad_unidades or 1,
    } for org in reporte.otros_organismos]

    attr_material = MATERIAL_ATTR.get(tipo)
    material = getattr(reporte, attr_material, None) if attr_material else None
    material = str(material).strip() if material else 'No registrado'

    fecha_emision = reporte.fecha_creacion or datetime.now()

    # Todas las horas del reporte se muestran en formato militar HH:MM:SS
    con_segundos = True

    # Vehículos afectados (lista dinámica)
    vehiculos_afectados = []
    if _es_incendio(tipo):
        for v in (getattr(reporte, 'vehiculos_afectados', None) or []):
            fila = {}
            for clave in ('marca', 'modelo', 'color', 'placa', 'serial_motor', 'anio',
                          'tipo', 'condicion', 'valor', 'perdidas', 'aseguradora',
                          'propietario', 'cedula', 'conductor', 'conductor_ci',
                          'valor_carga', 'perdida_carga', 'aseguradora_carga'):
                valor = v.get(clave)
                fila[clave] = str(valor).strip() if valor not in (None, '') else ''
            if any(fila.values()):
                vehiculos_afectados.append(fila)

    # Título acorde al subtipo cuando el reporte es de apoyo
    tipo_titulo = tipo
    if tipo == 'incendio_apoyo':
        tipo_titulo = 'incendio_' + (reporte.tipo_apoyo or 'estructura')
    nombre_servicio = NOMBRE_SERVICIO.get(tipo, (tipo or '').upper())
    titulo_seccion_2 = TITULO_SECCION_2.get(tipo, '2. DETALLE DEL SERVICIO')
    if tipo == 'incendio_apoyo':
        nombre_servicio = 'APOYO POR INCENDIOS - ' + NOMBRE_SERVICIO.get(tipo_titulo, '')
        titulo_seccion_2 = '2. APOYO POR INCENDIOS - ' + TITULO_SECCION_2.get(tipo_titulo, '').replace('2. DETALLE DEL ', '')

    # Personas afectadas / lesionados (APH y rescates)
    personas_afectadas = [{
        'nombre': p.nombre_apellido or '—',
        'cedula': p.cedula_pasaporte or '—',
        'edad': p.edad if p.edad is not None else '—',
        'sexo': p.sexo or '—',
        'lesion': p.lesion or '—',
        'residencia': p.residencia or '—',
    } for p in reporte.personas_afectadas]

    return {
        'logo': '',
        'reporte_id': reporte.id,
        'tipo_reporte': tipo,
        'nro_control': reporte.nro_control,
        'nombre_servicio': nombre_servicio,
        'titulo_seccion_2': titulo_seccion_2,
        'fecha_incidente': _formatear_fecha(reporte.fecha),
        'fecha_emision': fecha_emision.strftime('%d/%m/%Y %H:%M'),
        'clase_aviso': reporte.clase_aviso or '—',
        'receptor_aviso': reporte.receptor_aviso or '—',
        'receptor_cedula': reporte.receptor_cedula or '—',
        'horas': [
            {'etiqueta': 'Hora de Aviso', 'valor': _formatear_hora(reporte.hora_aviso, con_segundos)},
            {'etiqueta': 'Hora de Salida', 'valor': _formatear_hora(reporte.hora_salida, con_segundos)},
            {'etiqueta': 'Hora de Llegada', 'valor': _formatear_hora(reporte.hora_llegada, con_segundos)},
            {'etiqueta': 'Hora de Regreso', 'valor': _formatear_hora(reporte.hora_regreso, con_segundos)},
        ],
        'itinerario_ruta': reporte.itinerario_ruta or '—',
        'cuadrante_paz': reporte.cuadrante_paz or '—',
        'solicitante_nombre': reporte.solicitante_nombre or '—',
        'solicitante_cedula': reporte.solicitante_cedula or '—',
        'solicitante_telefono': reporte.solicitante_telefono or '—',
        'direccion': reporte.direccion or '—',
        'punto_referencia': reporte.punto_referencia or '—',
        'especifico': especifico,
        'vehiculos': vehiculos,
        'vehiculos_afectados': vehiculos_afectados,
        'descripcion_alarma': _nl2br_html(getattr(reporte, 'descripcion', None)) if getattr(reporte, 'descripcion', None) else '',
        'material_bomberil': material,
        'total_efectivos': len(personal),
        'jefe_comision': _formatear_personal(jefe),
        'conductor_unidad': _formatear_personal(conductor),
        'elaborado_por': _formatear_personal(elaborado),
        'combatientes': combatientes,
        'otros_organismos': otros_organismos,
        'personas_afectadas': personas_afectadas,
        'observaciones': _nl2br_html(reporte.observaciones_generales),
        'estado': reporte.estado or '—',
    }


def renderizar_html_reporte(reporte):
    """
    Renderiza el documento oficial del reporte como HTML plano (la misma
    plantilla usada para el PDF). Se usa en la vista de impresión/reimpresión
    del navegador y como insumo para la conversión a PDF.
    """
    from flask import render_template

    dto = serializar_reporte(reporte)
    dto['logo'] = obtener_logo_data_uri()
    return render_template('reportes/reporte_pdf.html', dto=dto)


def generar_pdf_reporte(reporte):
    """
    Genera los bytes del PDF del reporte.

    Estrategia de motores:
      1. WeasyPrint: mejor soporte de CSS Paged Media (usa @page, bordes,
         control de saltos de página). Requiere Pango en el servidor (Linux).
      2. xhtml2pdf: motor 100% Python (reportlab) que funciona en cualquier
         plataforma (incluido Windows sin GTK). Se usa como respaldo.

    Devuelve una tupla (bytes_pdf, nombre_del_motor_utilizado).
    """
    html = renderizar_html_reporte(reporte)

    weasyprint = _cargar_weasyprint()
    if weasyprint is not None:
        try:
            pdf = weasyprint.HTML(string=html).write_pdf()
            return pdf, 'WeasyPrint'
        except Exception:
            pass

    from xhtml2pdf import pisa

    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(html, dest=buffer, encoding='utf-8')
    if resultado.err:
        raise RuntimeError('No fue posible generar el PDF del reporte.')
    return buffer.getvalue(), 'xhtml2pdf'


@lru_cache(maxsize=1)
def _cargar_weasyprint():
    """
    Importa WeasyPrint una sola vez (se cachea el resultado). Devuelve el
    módulo si está disponible o None si la plataforma no tiene sus
    dependencias nativas (GTK/Pango en Windows), en cuyo caso se usa
    xhtml2pdf como motor de respaldo.
    """
    try:
        import weasyprint
        return weasyprint
    except Exception:
        return None


def motor_pdf_disponible():
    """
    Indica qué motor de PDF está disponible actualmente en el servidor.
    """
    return 'WeasyPrint' if _cargar_weasyprint() is not None else 'xhtml2pdf'