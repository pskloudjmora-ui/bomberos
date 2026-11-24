from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from datetime import datetime, time
import json
import re

from sqlalchemy.exc import IntegrityError
from app.models import (
    db, Usuario, Vehiculo, Reporte, ReporteVehiculoActuante, ReportePersonalActuante, ReporteOtroOrganismo,
    ReporteMatpelGLP, ReporteMatpelCombustible, ReporteMatpelQuimico, ReporteMatpelOtros,
    ReportePreHospitalario, ReporteServicioAgua, ReporteServicioInsectos, ReporteServicioAnimal,
    ReporteServicioAchicamiento, ReporteServicioBaldeo,
    ReporteAPHTraslado, ReporteAPHNoTraslado, ReporteAPHInterhospitalario, ReporteAPHSinTraslado,
    ReporteIncendio, ReporteRescateColision, ReporteRescateEspecializado, ReportePersonaAfectada,
    ReporteFalsaAlarma, ReporteAperturaPuerta, ReporteServicioPiscinas, ReporteServicioLluvias,
    ReporteInspeccionInsectos, ReporteBusquedaRescate
)
from app.services.pdf_service import generar_pdf_reporte, renderizar_html_reporte

reportes_bp = Blueprint('reportes', __name__)

# Mapeo de tipo_reporte con su clase de modelo SQLAlchemy correspondiente
REPORT_MODEL_MAP = {
    'matpel_glp': ReporteMatpelGLP,
    'matpel_combustible': ReporteMatpelCombustible,
    'matpel_quimico': ReporteMatpelQuimico,
    'matpel_otros': ReporteMatpelOtros,
    'falsa_alarma': ReporteFalsaAlarma,
    'pre_hospitalario': ReportePreHospitalario,
    'servicio_agua': ReporteServicioAgua,
    'servicio_insectos': ReporteServicioInsectos,
    'servicio_animal': ReporteServicioAnimal,
    'servicio_achicamiento': ReporteServicioAchicamiento,
    'servicio_baldeo': ReporteServicioBaldeo,
    # Nuevos: Atención Pre-Hospitalaria
    'aph_traslado': ReporteAPHTraslado,
    'aph_no_traslado': ReporteAPHNoTraslado,
    'aph_interhospitalario': ReporteAPHInterhospitalario,
    'aph_sin_traslado': ReporteAPHSinTraslado,
    # Nuevos: Incendios
    'incendio_estructura': ReporteIncendio,
    'incendio_apoyo': ReporteIncendio,
    'incendio_electrico': ReporteIncendio,
    'incendio_vehiculo': ReporteIncendio,
    'incendio_desechos': ReporteIncendio,
    'incendio_vegetacion': ReporteIncendio,
    'incendio_arbol': ReporteIncendio,
    # Nuevos: Rescate Colisión/Volcamiento
    'rescate_colision_con_lesionado': ReporteRescateColision,
    'rescate_colision_sin_lesionado': ReporteRescateColision,
    'rescate_volcamiento_con_lesionado': ReporteRescateColision,
    'rescate_volcamiento_sin_lesionado': ReporteRescateColision,
    # Nuevos: Rescate Especializado
    'rescate_ascensor': ReporteRescateEspecializado,
    'rescate_inmueble': ReporteRescateEspecializado,
    'rescate_tapiada': ReporteRescateEspecializado,
    'rescate_golpeada': ReporteRescateEspecializado,
    'rescate_caida': ReporteRescateEspecializado,
    'rescate_cadaver': ReporteRescateEspecializado,
    # Nuevos tipos de reporte
    'apertura_puerta': ReporteAperturaPuerta,
    'incendio_arbol_caido': ReporteIncendio,
    'servicio_piscinas': ReporteServicioPiscinas,
    'servicio_lluvias': ReporteServicioLluvias,
    'inspeccion_insectos': ReporteInspeccionInsectos,
    'siniestro_vial_con_lesionado': ReporteRescateColision,
    'siniestro_vial_sin_lesionado': ReporteRescateColision,
    'busqueda_rescate': ReporteBusquedaRescate,
}

# Prefijos correspondientes para la autogeneración del N° de Control
REPORT_PREFIX_MAP = {
    'matpel_glp': 'GLP',
    'matpel_combustible': 'COMB',
    'matpel_quimico': 'QUIM',
    'matpel_otros': 'GN',
    'falsa_alarma': 'FAL',
    'pre_hospitalario': 'APH',
    'servicio_agua': 'AGUA',
    'servicio_insectos': 'INS',
    'servicio_animal': 'ANIM',
    'servicio_achicamiento': 'ACHI',
    'servicio_baldeo': 'BALD',
    'aph_traslado': 'APH_TRAS',
    'aph_no_traslado': 'APH_NO_TRAS',
    'aph_interhospitalario': 'APH_INTER',
    'aph_sin_traslado': 'APH_SIN_TRAS',
    'incendio_estructura': 'INC_EST',
    'incendio_apoyo': 'INC_APOYO',
    'incendio_electrico': 'INC_ELEC',
    'incendio_vehiculo': 'INC_VEH',
    'incendio_desechos': 'INC_DESE',
    'incendio_vegetacion': 'INC_VEG',
    'incendio_arbol': 'INC_ARB',
    'rescate_colision_con_lesionado': 'RES_COL_L',
    'rescate_colision_sin_lesionado': 'RES_COL_S',
    'rescate_volcamiento_con_lesionado': 'RES_VOL_L',
    'rescate_volcamiento_sin_lesionado': 'RES_VOL_S',
    'rescate_ascensor': 'RES_ASC',
    'rescate_inmueble': 'RES_INM',
    'rescate_tapiada': 'RES_TAP',
    'rescate_golpeada': 'RES_GOL',
    'rescate_caida': 'RES_CAID',
    'rescate_cadaver': 'RES_CAD',
    'apertura_puerta': 'APUE',
    'incendio_arbol_caido': 'INC_ARBC',
    'servicio_piscinas': 'PISC',
    'servicio_lluvias': 'LLUV',
    'inspeccion_insectos': 'INSP_INS',
    'siniestro_vial_con_lesionado': 'SINV_CL',
    'siniestro_vial_sin_lesionado': 'SINV_SL',
    'busqueda_rescate': 'BUSQ',
}

# Títulos de cabecera legibles para la plantilla crear.html
REPORT_TITLE_MAP = {
    'matpel_glp': 'Reporte MATPEL - Control de Escape de GLP',
    'matpel_combustible': 'Reporte MATPEL - Derrame de Combustible',
    'matpel_quimico': 'Reporte MATPEL - Derrame de Sustancia Química',
    'matpel_otros': 'Reporte MATPEL - Control de Gas Natural',
    'falsa_alarma': 'Falsa Alarma por Incendio de Estructura o Vehículo',
    'pre_hospitalario': 'Atención Pre-Hospitalaria / Traslado Rutinario',
    'servicio_agua': 'Servicio Especial - Abastecimiento de Agua',
    'servicio_insectos': 'Servicio Especial - Control y Re-ubicación de Insectos',
    'servicio_animal': 'Servicio Especial - Control de Animal Doméstico',
    'servicio_achicamiento': 'Servicio Especial - Achicamiento por Aguas Estancadas',
    'servicio_baldeo': 'Servicio Especial - Baldeo de Agua',
    'aph_traslado': 'Atención Pre-Hospitalaria - Traslado de Emergencia',
    'aph_no_traslado': 'Atención Pre-Hospitalaria - Traslado No Realizado',
    'aph_interhospitalario': 'Atención Pre-Hospitalaria - Traslados Interhospitalarios',
    'aph_sin_traslado': 'Atención Pre-Hospitalaria Sin Traslado',
    'incendio_estructura': 'Reporte de Incendio de Estructura',
    'incendio_apoyo': 'Reporte de Apoyo por Incendios',
    'incendio_electrico': 'Reporte de Incendio de Equipos Eléctricos',
    'incendio_vehiculo': 'Reporte de Incendio de Vehículo',
    'incendio_desechos': 'Reporte de Incendio de Desechos Sólidos',
    'incendio_vegetacion': 'Reporte de Incendio de Vegetación y/o Forestal',
    'incendio_arbol': 'Reporte de Incendio de Árbol',
    'rescate_colision_con_lesionado': 'Rescate por Colisión con Lesionado',
    'rescate_colision_sin_lesionado': 'Rescate por Colisión sin Lesionado',
    'rescate_volcamiento_con_lesionado': 'Rescate por Volcamiento con Lesionado',
    'rescate_volcamiento_sin_lesionado': 'Rescate por Volcamiento sin Lesionado',
    'rescate_ascensor': 'Rescate de Persona Incomunicada en Ascensor',
    'rescate_inmueble': 'Rescate de Persona Incomunicada en Inmueble',
    'rescate_tapiada': 'Rescate de Persona Tapiada',
    'rescate_golpeada': 'Rescate de Persona Golpeada por',
    'rescate_caida': 'Rescate de Persona Caída en Altura',
    'rescate_cadaver': 'Rescate de Cadáver',
    'apertura_puerta': 'Recuperación de Llaves / Apertura de Puerta',
    'incendio_arbol_caido': 'Control de Peligro por Árbol Caído',
    'servicio_piscinas': 'Recorrido por Piscinas y Balnearios',
    'servicio_lluvias': 'Recorrido por Lluvias',
    'inspeccion_insectos': 'Inspección - Control y Reubicación de Insectos',
    'siniestro_vial_con_lesionado': 'Siniestro Vial con Lesionado',
    'siniestro_vial_sin_lesionado': 'Siniestro Vial sin Lesionado',
    'busqueda_rescate': 'Operaciones de Búsqueda y Rescate',
}

# Campos específicos que corresponden a cada clase de reporte
REPORT_FIELDS_MAP = {
    'matpel_glp': [
        'clasificacion_servicio', 'nombre_producto', 'un_numero', 'riesgo_producto', 'tipo_almacenamiento',
        'serial_cilindro', 'certificado_bomberil', 'nro_certificado', 'propietario_nombre', 'propietario_rif_ci',
        'empresa_distribuidora', 'hoja_seguridad', 'extintor', 'equipo_derrame'
    ],
    'matpel_combustible': [
        'tipo_combustible', 'tipo_almacenamiento', 'un_numero', 'capacidad_tanque_litros',
        'riesgo_producto', 'tipo_estructura', 'propietario_nombre', 'propietario_rif_ci',
        'propietario_telefono', 'empresa_distribuidora',
        'mitigacion_efectuada', 'cantidad_estimada_derrame'
    ],
    'matpel_quimico': [
        'nombre_sustancia', 'un_numero', 'riesgos_especificos',
        'materiales_absorbentes_usados', 'materiales_neutralizantes_usados', 'acciones_mitigacion',
        'origen_derrame', 'tipo_estructura', 'propietario_nombre', 'propietario_rif_ci',
        'propietario_telefono', 'empresa_distribuidora',
        'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color'
    ],
    'matpel_otros': [
        'clasificacion_servicio', 'nombre_producto', 'un_numero', 'riesgo_producto', 'tipo_almacenamiento',
        'serial_cilindro', 'certificado_bomberil', 'nro_certificado', 'propietario_nombre', 'propietario_rif_ci',
        'empresa_distribuidora', 'hoja_seguridad', 'extintor', 'equipo_derrame'
    ],
    'falsa_alarma': [
        'tipo_alarma', 'descripcion'
    ],
    'pre_hospitalario': [
        'paciente_nombre', 'paciente_edad', 'paciente_genero', 'paciente_cedula',
        'condicion_paciente', 'signos_vitales_tension', 'signos_vitales_pulso',
        'signos_vitales_fr', 'signos_vitales_temperatura',
        'centro_traslado', 'material_medico_utilizado', 'recomendaciones'
    ],
    'servicio_agua': [
        'clasificacion_servicio', 'material_usado', 'litros_distribuidos', 'beneficiarios_estimados'
    ],
    'servicio_insectos': [
        'tipo_insecto', 'clasificacion_riesgo', 'condicion_actual', 'metodo_control',
        'materiales_utilizados', 'recomendaciones'
    ],
    'servicio_animal': [
        'tipo_animal', 'raza_descripcion', 'condicion_animal', 'destino_animal',
        'recomendaciones_tecnicas'
    ],
    'servicio_achicamiento': [
        'condicion_inmueble', 'causa_inundacion', 'bombas_usadas', 'tiempo_operacion',
        'nivel_agua_inicial', 'nivel_agua_final', 'inspeccion_tecnica_observaciones'
    ],
    'servicio_baldeo': [
        'motivo_baldeo', 'area_afectada', 'limpieza_vias_efectuada', 'litros_agua_utilizados',
        'observaciones_baldeo'
    ],
    'aph_traslado': [
        'causa_traslado', 'recomendaciones',
        'signos_vitales_pa', 'signos_vitales_fc', 'signos_vitales_fr', 'signos_vitales_temperatura',
        'glasgow_apertura_ocular', 'glasgow_respuesta_verbal', 'glasgow_respuesta_motora', 'glasgow_total',
        'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_miembro_superior_d',
        'regla_9_miembro_superior_i', 'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i', 'regla_9_total',
        'procedimiento_paraclinico', 'medicinas_usadas', 'material_medico_usado',
        'centro_hospitalario', 'medico_recibe', 'medico_cedula', 'medico_msds', 'medico_firma',
        'rechazo_nombre', 'rechazo_cedula', 'rechazo_firma'
    ],
    'aph_no_traslado': [
        'causa_traslado', 'recomendaciones',
        'signos_vitales_pa', 'signos_vitales_fc', 'signos_vitales_fr', 'signos_vitales_temperatura',
        'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_miembro_superior_d',
        'regla_9_miembro_superior_i', 'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i', 'regla_9_total',
        'procedimiento_paraclinico', 'medicinas_usadas', 'material_medico_usado',
        'motivo_no_traslado', 'indicaciones_dejadas', 'paciente_firma',
        'rechazo_nombre', 'rechazo_cedula', 'rechazo_firma'
    ],
    'aph_interhospitalario': [
        'causa_traslado', 'recomendaciones',
        'signos_vitales_pa', 'signos_vitales_fc', 'signos_vitales_fr', 'signos_vitales_temperatura',
        'glasgow_apertura_ocular', 'glasgow_respuesta_verbal', 'glasgow_respuesta_motora', 'glasgow_total',
        'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_miembro_superior_d',
        'regla_9_miembro_superior_i', 'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i', 'regla_9_total',
        'procedimiento_paraclinico', 'medicinas_usadas', 'material_medico_usado',
        'centro_origen', 'medico_origen', 'centro_destino',
        'medico_recibe', 'medico_cedula', 'medico_msds', 'medico_firma',
        'rechazo_nombre', 'rechazo_cedula', 'rechazo_firma'
    ],
    'aph_sin_traslado': [
        'causa_traslado', 'recomendaciones',
        'signos_vitales_pa', 'signos_vitales_fc', 'signos_vitales_fr', 'signos_vitales_temperatura',
        'glasgow_apertura_ocular', 'glasgow_respuesta_verbal', 'glasgow_respuesta_motora', 'glasgow_total',
        'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_miembro_superior_d',
        'regla_9_miembro_superior_i', 'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i', 'regla_9_total',
        'procedimiento_paraclinico', 'medicinas_usadas', 'material_medico_usado',
        'conducta_adoptada', 'indicaciones_dejadas',
        'rechazo_nombre', 'rechazo_cedula', 'rechazo_firma'
    ],
    'incendio_estructura': [
        'subtipo_incendio', 'clase_incendio', 'tipo_estructura', 'lugar_desarrollo', 'presunto_punto_origen',
        'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci', 'tipo_equipo_contra_incendio',
        'evaluacion_preliminar',
        'salida_primera_maquina', 'salida_segunda_maquina', 'salida_ambulancia',
        'salida_unidad_adicional', 'salida_unidad_adicional_nombre',
        'inmueble_propietario_nombre', 'inmueble_propietario_cedula', 'inmueble_propietario_telefono',
        'inmueble_descripcion', 'inmueble_valor', 'inmueble_perdidas', 'inmueble_aseguradora',
        'mueble_propietario', 'mueble_propietario_ci', 'mueble_valor', 'mueble_perdidas',
        'mueble_aseguradora', 'mueble_condicion', 'lugar_a_cargo'
    ],
    'incendio_apoyo': [
        'subtipo_incendio', 'tipo_apoyo', 'tipo_incendio',
        'clase_incendio', 'tipo_estructura', 'lugar_desarrollo', 'presunto_punto_origen',
        'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci', 'tipo_equipo_contra_incendio',
        'evaluacion_preliminar',
        'salida_primera_maquina', 'salida_segunda_maquina', 'salida_ambulancia',
        'salida_unidad_adicional', 'salida_unidad_adicional_nombre',
        'inmueble_propietario_nombre', 'inmueble_propietario_cedula', 'inmueble_propietario_telefono',
        'inmueble_descripcion', 'inmueble_valor', 'inmueble_perdidas', 'inmueble_aseguradora',
        'mueble_propietario', 'mueble_propietario_ci', 'mueble_valor', 'mueble_perdidas',
        'mueble_aseguradora', 'mueble_condicion', 'lugar_a_cargo',
        'sistema_electrico_tipo', 'sistema_electrico_capacidad', 'sistema_electrico_uso',
        'sistema_electrico_serial', 'sistema_electrico_propiedad', 'sistema_electrico_rif',
        'desperdicio_materia', 'desperdicio_cantidad', 'desperdicio_recuperable',
        'arbol_edad', 'arbol_longitud', 'arbol_circunferencia', 'arbol_especie',
        'tipo_terreno', 'tipo_vegetacion', 'extension_terreno', 'extension_terreno_afectada', 'coordenadas',
        'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color',
        'vehiculo_anio', 'vehiculo_tipo',
        'propietario_nombre', 'propietario_cedula', 'propietario_edad', 'propietario_telefono'
    ],
    'incendio_electrico': [
        'subtipo_incendio', 'hora_control', 'hora_extincion_total',
        'litros_agua_utilizados', 'metodos_extincion', 'tecnicas_extincion',
        'tipo_equipo_contra_incendio', 'evaluacion_preliminar',
        'sistema_electrico_tipo', 'sistema_electrico_capacidad', 'sistema_electrico_uso',
        'sistema_electrico_serial', 'sistema_electrico_propiedad', 'sistema_electrico_rif'
    ],
    'incendio_vehiculo': [
        'subtipo_incendio', 'clase_incendio', 'lugar_desarrollo', 'presunto_punto_origen',
        'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci', 'tipo_equipo_contra_incendio',
        'evaluacion_preliminar',
        'salida_primera_maquina', 'salida_segunda_maquina', 'salida_ambulancia',
        'salida_unidad_adicional', 'salida_unidad_adicional_nombre',
        # Columnas legacy del vehículo afectado (respaldo del JSON)
        'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color',
        'vehiculo_anio', 'vehiculo_tipo',
        'propietario_nombre', 'propietario_cedula', 'propietario_edad', 'propietario_telefono'
    ],
    'incendio_desechos': [
        'subtipo_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'metodos_extincion', 'tecnicas_extincion',
        'tipo_equipo_contra_incendio', 'evaluacion_preliminar',
        'salida_primera_maquina', 'salida_segunda_maquina',
        'salida_unidad_adicional', 'salida_unidad_adicional_nombre',
        'desperdicio_materia', 'desperdicio_cantidad', 'desperdicio_recuperable'
    ],
    'incendio_vegetacion': [
        'subtipo_incendio', 'tipo_incendio', 'hora_control', 'hora_extincion_total',
        'litros_agua_utilizados', 'metodos_extincion', 'tecnicas_extincion',
        'tipo_equipo_contra_incendio', 'evaluacion_preliminar',
        'salida_primera_maquina', 'salida_segunda_maquina',
        'tipo_terreno', 'tipo_vegetacion', 'extension_terreno', 'extension_terreno_afectada', 'coordenadas'
    ],
    'incendio_arbol': [
        'subtipo_incendio', 'hora_control', 'hora_extincion_total',
        'litros_agua_utilizados', 'metodos_extincion', 'tecnicas_extincion',
        'tipo_equipo_contra_incendio', 'evaluacion_preliminar',
        'salida_primera_maquina',
        'arbol_edad', 'arbol_longitud', 'arbol_circunferencia', 'arbol_especie'
    ],
    'rescate_colision_con_lesionado': [
        'subtipo_rescate', 'vehiculos_involucrados_json',
        'observaciones_custodio', 'vehiculo_cargo_nombre', 'vehiculo_cargo_cedula', 'vehiculo_cargo_telefono'
    ],
    'rescate_colision_sin_lesionado': [
        'subtipo_rescate', 'vehiculos_involucrados_json',
        'observaciones_custodio', 'vehiculo_cargo_nombre', 'vehiculo_cargo_cedula', 'vehiculo_cargo_telefono'
    ],
    'rescate_volcamiento_con_lesionado': [
        'subtipo_rescate', 'vehiculos_involucrados_json',
        'observaciones_custodio', 'vehiculo_cargo_nombre', 'vehiculo_cargo_cedula', 'vehiculo_cargo_telefono'
    ],
    'rescate_volcamiento_sin_lesionado': [
        'subtipo_rescate', 'vehiculos_involucrados_json',
        'observaciones_custodio', 'vehiculo_cargo_nombre', 'vehiculo_cargo_cedula', 'vehiculo_cargo_telefono'
    ],
    'rescate_ascensor': [
        'subtipo_rescate', 'tipo_servicio', 'despliegue_material_usado', 'salida_ambulancia'
    ],
    'rescate_inmueble': [
        'subtipo_rescate', 'tipo_servicio', 'despliegue_material_usado', 'salida_ambulancia'
    ],
    'rescate_tapiada': [
        'subtipo_rescate', 'tipo_servicio', 'motivo_tapiada',
        'despliegue_material_usado', 'salida_ambulancia'
    ],
    'rescate_golpeada': [
        'subtipo_rescate', 'tipo_servicio', 'motivo_golpeada',
        'golpeada_por_vehiculo', 'golpeada_vehiculo_marca', 'golpeada_vehiculo_modelo',
        'golpeada_vehiculo_placa', 'golpeada_vehiculo_color',
        'golpeada_conductor_nombre', 'golpeada_conductor_ci', 'golpeada_conductor_telefono',
        'despliegue_material_usado', 'salida_ambulancia'
    ],
    # Caída en altura: se registran los datos del lesionado (tabla
    # reporte_personas_afectadas) y el tipo de terreno, en lugar del
    # despliegue operacional.
    'rescate_caida': [
        'subtipo_rescate', 'tipo_terreno', 'despliegue_material_usado',
        'salida_ambulancia', 'salida_primera_maquina'
    ],
    # Cadáver: solo datos del cadáver y ubicación del hallazgo.
    'rescate_cadaver': [
        'subtipo_rescate', 'despliegue_material_usado',
        'cadaver_nombre', 'cadaver_cedula', 'cadaver_edad', 'cadaver_sexo', 'cadaver_ubicacion'
    ],
    'siniestro_vial_con_lesionado': [
        'subtipo_rescate', 'tipo_siniestro', 'vehiculos_involucrados_json',
        'observaciones_custodio', 'vehiculo_cargo_nombre', 'vehiculo_cargo_cedula', 'vehiculo_cargo_telefono',
        'salida_primera_maquina', 'salida_segunda_maquina', 'salida_ambulancia',
        'salida_unidad_adicional', 'salida_unidad_adicional_nombre'
    ],
    'siniestro_vial_sin_lesionado': [
        'subtipo_rescate', 'tipo_siniestro', 'vehiculos_involucrados_json',
        'observaciones_custodio', 'vehiculo_cargo_nombre', 'vehiculo_cargo_cedula', 'vehiculo_cargo_telefono',
        'salida_primera_maquina', 'salida_segunda_maquina', 'salida_ambulancia',
        'salida_unidad_adicional', 'salida_unidad_adicional_nombre'
    ],
    'busqueda_rescate': [
        'tipo_zona', 'material_usado',
        'salida_primera_maquina', 'salida_segunda_maquina', 'salida_ambulancia',
        'salida_unidad_adicional', 'salida_unidad_adicional_nombre'
    ],
    # Apertura de puerta / recuperación de llaves: datos del propietario.
    'apertura_puerta': [
        'propietario_nombre', 'propietario_cedula', 'propietario_telefono', 'inmueble_direccion'
    ],
    # Árbol caído: parámetros de incendio de estructura/vehículo según el
    # objeto afectado (se filtran en el formulario con el check de cabecera).
    'incendio_arbol_caido': [
        'subtipo_incendio', 'arbol_afecto', 'tipo_estructura', 'lugar_desarrollo',
        'presunto_punto_origen',
        'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'tipo_equipo_contra_incendio', 'evaluacion_preliminar',
        'inmueble_propietario_nombre', 'inmueble_propietario_cedula', 'inmueble_propietario_telefono',
        'inmueble_descripcion', 'inmueble_valor', 'inmueble_perdidas', 'inmueble_aseguradora',
        'mueble_propietario', 'mueble_propietario_ci', 'mueble_valor', 'mueble_perdidas',
        'mueble_aseguradora', 'mueble_condicion', 'lugar_a_cargo',
        'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color',
        'vehiculo_anio', 'vehiculo_tipo',
        'propietario_nombre', 'propietario_cedula', 'propietario_edad', 'propietario_telefono'
    ],
    'servicio_piscinas': [
        'clasificacion_servicio', 'material_usado', 'litros_distribuidos', 'beneficiarios_estimados'
    ],
    'servicio_lluvias': [
        'clasificacion_servicio', 'material_usado', 'litros_distribuidos', 'beneficiarios_estimados'
    ],
    'inspeccion_insectos': [
        'tipo_insecto', 'clasificacion_riesgo', 'condicion_actual',
        'materiales_utilizados', 'recomendaciones'
    ],
}


def _parsear_vehiculos_involucrados():
    """Lee las listas dinamicas veh_inv_*[] y devuelve la lista de dicts."""
    claves = ['marca', 'modelo', 'placa', 'color', 'anio', 'tipo', 'propietario', 'cedula', 'telefono', 'edad', 'conductor', 'conductor_ci', 'conductor_tel']
    listas = {c: request.form.getlist('veh_inv_%s[]' % c) for c in claves}
    total = max((len(v) for v in listas.values()), default=0)
    vehiculos = []
    for i in range(total):
        registro = {c: (listas[c][i] if i < len(listas[c]) else '').strip() for c in claves}
        if any(registro.values()):
            vehiculos.append(registro)
    return vehiculos


def resolver_personal_seleccionado(clave_usuario_id, clave_nombre, clave_ci, clave_rango):
    """
    Resuelve los datos de un bombero del formulario: si se eligió un usuario
    del listado (select), toma nombre, cédula y rango desde la BD; en caso
    contrario usa los campos de texto manuales (compatibilidad).
    Devuelve (nombre_completo, cedula, rango).
    """
    usuario_id = request.form.get(clave_usuario_id)
    if usuario_id:
        try:
            usuario = db.session.get(Usuario, int(usuario_id))
        except (TypeError, ValueError):
            usuario = None
        if usuario:
            return f'{usuario.nombre} {usuario.apellido}', usuario.cedula, usuario.rango
    return request.form.get(clave_nombre), request.form.get(clave_ci), request.form.get(clave_rango)


# Tipos de dato por campo específico del formulario
CAMPOS_BOOLEANOS = {
    'certificado_bomberil', 'hoja_seguridad', 'extintor', 'equipo_derrame',
    'limpieza_vias_efectuada', 'vehiculo_afecto', 'medico_firma',
    'rechazo_firma', 'hubo_propagacion', 'poseia_equipos', 'fue_usado',
}

CAMPOS_ENTEROS = {
    'paciente_edad', 'signos_vitales_pulso', 'signos_vitales_fr',
    'litros_distribuidos', 'beneficiarios_estimados', 'litros_agua_utilizados',
    'signos_vitales_fc', 'glasgow_apertura_ocular', 'glasgow_respuesta_verbal',
    'glasgow_respuesta_motora', 'glasgow_total', 'propietario_edad',
    'despliegue_cantidad_bomberos',
}

CAMPOS_DECIMALES = {
    'cantidad_estimada_derrame', 'capacidad_tanque_litros',
    'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_total',
    'regla_9_miembro_superior_d', 'regla_9_miembro_superior_i',
    'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i',
    'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
    'inmueble_valor', 'inmueble_perdidas', 'mueble_valor', 'mueble_perdidas',
}

# Campos de tipo hora (columnas db.Time) que no forman parte de la cabecera
CAMPOS_HORA = {
    'hora_control', 'hora_extincion_total',
    'salida_primera_maquina', 'salida_segunda_maquina', 'salida_ambulancia',
    'salida_unidad_adicional',
}


def _a_entero(valor):
    """Convierte a entero sin lanzar excepción (None si no es válido)."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def parse_field_value(field_name, raw_val):
    """
    Parsea los valores raw provenientes del formulario de acuerdo a sus tipos
    de datos requeridos en la BD. Un valor no numérico produce un error de
    validación en lugar de guardarse silenciosamente como 0.
    """
    if raw_val is None or raw_val == '':
        return None
    if field_name in CAMPOS_BOOLEANOS:
        return raw_val in ['Si', 'on', 'true', '1', True]
    etiqueta = field_name.replace('_', ' ')
    if field_name in CAMPOS_ENTEROS:
        try:
            return int(raw_val)
        except (TypeError, ValueError):
            raise ValueError(f'El campo "{etiqueta}" debe ser un número entero.')
    if field_name in CAMPOS_DECIMALES:
        try:
            return float(str(raw_val).replace(',', '.'))
        except (TypeError, ValueError):
            raise ValueError(f'El campo "{etiqueta}" debe ser un número.')
    if field_name in CAMPOS_HORA:
        try:
            return _parsear_hora(str(raw_val).strip())
        except (TypeError, ValueError):
            raise ValueError(f'El campo "{etiqueta}" debe tener formato de hora militar HH:MM:SS (00:00:00 a 23:59:59).')
    return raw_val


def _siguiente_nro_control(prefix, tipo_reporte):
    """
    Calcula el siguiente número de control tomando el mayor consecutivo
    existente del tipo en el año. A diferencia de contar filas, esto no genera
    duplicados cuando se elimina un reporte.

    El prefijo es único por tipo de reporte, así que se filtra por él en lugar
    de por ``tipo_reporte`` (que solo guarda la identidad polimórfica genérica).
    """
    anio = datetime.now().year
    base = f'{prefix}-{anio}-'
    numeros = db.session.query(Reporte.nro_control).filter(
        Reporte.nro_control.like(f'{base}%'),
    ).all()

    maximo = 0
    for (nro_control,) in numeros:
        try:
            maximo = max(maximo, int(str(nro_control).rsplit('-', 1)[-1]))
        except (TypeError, ValueError):
            continue
    return f'{base}{maximo + 1:04d}'


_HORA_24H_RE = re.compile(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$')


def _parsear_hora(valor):
    """
    Normaliza y valida una hora en formato militar de 24 horas (00:00:00 a
    23:59:59). Acepta HH:MM y HH:MM:SS con ':' o '.' como separador, y el
    formato compacto de teclado numérico HHMM / HHMMSS. Devuelve datetime.time
    y lanza ValueError si el formato o los rangos no son válidos.
    """
    texto = str(valor or '').strip()
    # Formato compacto sin separadores (típico de teclados numéricos)
    if re.fullmatch(r'\d{4}|\d{6}', texto):
        if len(texto) == 4:
            texto = f'{texto[:2]}:{texto[2:]}'
        else:
            texto = f'{texto[:2]}:{texto[2:4]}:{texto[4:]}'
    texto = texto.replace('.', ':')
    coincidencia = _HORA_24H_RE.match(texto)
    if not coincidencia:
        raise ValueError('formato de hora no válido')
    hora = int(coincidencia.group(1))
    minuto = int(coincidencia.group(2))
    segundo = int(coincidencia.group(3) or 0)
    if hora > 23 or minuto > 59 or segundo > 59:
        raise ValueError('formato de hora no válido')
    return time(hora, minuto, segundo)


def _leer_cabecera(form):
    """
    Valida y normaliza los datos comunes del reporte.
    Devuelve (diccionario_de_datos, lista_de_errores).
    """
    errores = []

    fecha_valor = (form.get('fecha') or '').strip()
    fecha = None
    if not fecha_valor:
        errores.append('La fecha del evento es obligatoria.')
    else:
        try:
            fecha = datetime.strptime(fecha_valor, '%Y-%m-%d').date()
        except ValueError:
            errores.append('La fecha del evento no es válida.')

    horas = {}
    for campo, etiqueta in (
        ('hora_aviso', 'hora de aviso'),
        ('hora_salida', 'hora de salida'),
        ('hora_llegada', 'hora de llegada'),
        ('hora_regreso', 'hora de regreso'),
    ):
        valor = (form.get(campo) or '').strip()
        if not valor:
            errores.append(f'La {etiqueta} es obligatoria.')
            horas[campo] = None
            continue
        try:
            horas[campo] = _parsear_hora(valor)
        except ValueError:
            errores.append(f'La {etiqueta} no es válida (formato militar HH:MM:SS, de 00:00:00 a 23:59:59).')
            horas[campo] = None

    clase_aviso = (form.get('clase_aviso') or '').strip()
    if not clase_aviso:
        errores.append('La clase de aviso es obligatoria.')

    receptor_aviso = (form.get('receptor_aviso') or '').strip()
    if not receptor_aviso:
        errores.append('Debe indicar quién recibió el aviso.')

    direccion = (form.get('direccion') or '').strip()
    if not direccion:
        errores.append('La dirección del evento es obligatoria.')

    itinerario_ruta = (form.get('itinerario_ruta') or '').strip() or None
    cuadrante_paz = (form.get('cuadrante_paz') or '').strip() or None

    return {
        'fecha': fecha,
        'clase_aviso': clase_aviso,
        'receptor_aviso': receptor_aviso,
        'direccion': direccion,
        'itinerario_ruta': itinerario_ruta,
        'cuadrante_paz': cuadrante_paz,
        **horas,
    }, errores


@reportes_bp.route('/crear/<tipo_reporte>', methods=['GET', 'POST'])
@login_required
def crear_reporte(tipo_reporte):
    """
    Controlador dinámico unificado que procesa la creación de todos los tipos
    de reportes de actuación.
    """
    if tipo_reporte not in REPORT_MODEL_MAP:
        flash('Tipo de reporte no válido.', 'danger')
        return redirect(url_for('main.index'))

    model_class = REPORT_MODEL_MAP[tipo_reporte]
    prefix = REPORT_PREFIX_MAP[tipo_reporte]
    title = REPORT_TITLE_MAP[tipo_reporte]
    fields = REPORT_FIELDS_MAP[tipo_reporte]

    # En el reporte de caída en altura no se solicitan las secciones de
    # vehículos, personal actuante ni organismos de apoyo.
    incluye_secciones_operativas = tipo_reporte not in ('rescate_caida', 'rescate_cadaver')

    if request.method == 'POST':
        try:
            # 1. VALIDAR DATOS COMUNES DE CABECERA
            cabecera, errores = _leer_cabecera(request.form)
            if errores:
                for error in errores:
                    flash(error, 'danger')
                return redirect(url_for('reportes.crear_reporte', tipo_reporte=tipo_reporte))

            # 2. AUTOGENERAR N° DE CONTROL SECUENCIAL ÚNICO
            nro_control = _siguiente_nro_control(prefix, tipo_reporte)

            solicitante_nombre = (request.form.get('solicitante_nombre') or '').strip() or None
            solicitante_cedula = (request.form.get('solicitante_cedula') or '').strip() or None
            solicitante_telefono = (request.form.get('solicitante_telefono') or '').strip() or None
            receptor_cedula = (request.form.get('receptor_cedula') or '').strip() or None
            punto_referencia = (request.form.get('punto_referencia') or '').strip() or None
            observaciones_generales = (request.form.get('observaciones_generales') or '').strip() or None

            # 3. EXTRAER Y PARSEAR CAMPOS ESPECÍFICOS DE LA SUBCLASE
            specific_kwargs = {}
            for field in fields:
                raw_val = request.form.get(field)
                # Si el campo tiene opción "Otro", usar el valor del input de texto
                if raw_val == 'Otro':
                    otro_val = (request.form.get(f'{field}_otro') or '').strip()
                    if otro_val:
                        raw_val = otro_val
                specific_kwargs[field] = parse_field_value(field, raw_val)

            # "¿A dónde se propagó?" solo se guarda si se marcó "Hubo Propagación"
            if 'propagacion_donde' in specific_kwargs and not specific_kwargs.get('hubo_propagacion'):
                specific_kwargs['propagacion_donde'] = None

            # Cascada de equipos: lo dependiente solo se guarda si el checkbox
            # padre está marcado (evita datos huérfanos y campos en el PDF).
            if 'poseia_equipos' in specific_kwargs and not specific_kwargs.get('poseia_equipos'):
                specific_kwargs['fue_usado'] = False
                specific_kwargs['por_quien_uso'] = None
                specific_kwargs['por_quien_ci'] = None
                specific_kwargs['tipo_equipo_contra_incendio'] = None
            if 'fue_usado' in specific_kwargs and not specific_kwargs.get('fue_usado'):
                specific_kwargs['por_quien_uso'] = None
                specific_kwargs['por_quien_ci'] = None
                specific_kwargs['tipo_equipo_contra_incendio'] = None

            # Rescate golpeada: datos del vehículo solo si fue golpeada por vehículo
            if 'golpeada_por_vehiculo' in specific_kwargs and not specific_kwargs.get('golpeada_por_vehiculo'):
                for c in ('golpeada_vehiculo_marca', 'golpeada_vehiculo_modelo', 'golpeada_vehiculo_placa',
                          'golpeada_vehiculo_color', 'golpeada_conductor_nombre',
                          'golpeada_conductor_ci', 'golpeada_conductor_telefono'):
                    specific_kwargs[c] = None

            # MATPEL quimico: limpiar grupo inactivo segun el origen del derrame
            if 'origen_derrame' in specific_kwargs:
                if specific_kwargs.get('origen_derrame') != 'vehiculo':
                    for c in ('vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color'):
                        specific_kwargs[c] = None
                if specific_kwargs.get('origen_derrame') != 'estructura':
                    for c in ('tipo_estructura', 'propietario_nombre', 'propietario_rif_ci',
                              'propietario_telefono', 'empresa_distribuidora'):
                        specific_kwargs[c] = None

            # 4. DEFINIR SUBTIPOS Y DATOS ADICIONALES SEGÚN EL TIPO
            extra_kwargs = {}
            # Subtipo para incendios
            if tipo_reporte.startswith('incendio_'):
                subtipos_map = {
                    'incendio_estructura': 'estructura', 'incendio_apoyo': 'apoyo',
                    'incendio_electrico': 'electrico', 'incendio_vehiculo': 'vehiculo',
                    'incendio_desechos': 'desechos', 'incendio_vegetacion': 'vegetacion',
                    'incendio_arbol': 'arbol', 'incendio_arbol_caido': 'arbol_caido',
                }
                extra_kwargs['subtipo_incendio'] = subtipos_map.get(tipo_reporte, tipo_reporte.replace('incendio_', ''))

                # Vehículos afectados (lista dinámica, aplica a vehículo y apoyo)
                claves_va = [
                    'marca', 'modelo', 'color', 'placa', 'serial_motor', 'anio',
                    'valor', 'perdidas', 'aseguradora', 'propietario', 'cedula',
                    'conductor', 'conductor_ci', 'valor_carga', 'perdida_carga',
                    'aseguradora_carga', 'condicion',
                ]
                columnas_va = {clave: request.form.getlist(f'va_{clave}[]') for clave in claves_va}
                vehiculos_afectados = []
                for i in range(max((len(v) for v in columnas_va.values()), default=0)):
                    registro = {}
                    for clave in claves_va:
                        valores = columnas_va[clave]
                        registro[clave] = (valores[i] if i < len(valores) else '').strip()
                    if any(registro.values()):
                        vehiculos_afectados.append(registro)
                if vehiculos_afectados:
                    extra_kwargs['vehiculos_afectados_json'] = json.dumps(
                        vehiculos_afectados, ensure_ascii=False
                    )
                    # Respaldo en las columnas legacy (primer vehículo)
                    primero = vehiculos_afectados[0]
                    extra_kwargs.update({
                        'vehiculo_marca': primero.get('marca') or None,
                        'vehiculo_modelo': primero.get('modelo') or None,
                        'vehiculo_placa': primero.get('placa') or None,
                        'vehiculo_color': primero.get('color') or None,
                        'vehiculo_anio': primero.get('anio') or None,
                        'propietario_nombre': primero.get('propietario') or None,
                        'propietario_cedula': primero.get('cedula') or None,
                    })
            # Vehículos involucrados (lista dinámica veh_inv_*) para MATPEL
            if tipo_reporte in ('matpel_glp', 'matpel_otros', 'matpel_combustible'):
                vehiculos_lista = _parsear_vehiculos_involucrados()
                if vehiculos_lista:
                    destino = 'vehiculos_involucrados' if tipo_reporte == 'matpel_combustible' else 'vehiculos_involucrados_json'
                    specific_kwargs[destino] = json.dumps(vehiculos_lista, ensure_ascii=False)

            # Subtipo para rescate colisión/volcamiento y siniestro vial
            if (tipo_reporte.startswith('rescate_colision_') or tipo_reporte.startswith('rescate_volcamiento_')
                    or tipo_reporte.startswith('siniestro_vial_')):
                subtipos_map = {
                    'rescate_colision_con_lesionado': 'colision_con_lesionado',
                    'rescate_colision_sin_lesionado': 'colision_sin_lesionado',
                    'rescate_volcamiento_con_lesionado': 'volcamiento_con_lesionado',
                    'rescate_volcamiento_sin_lesionado': 'volcamiento_sin_lesionado',
                    'siniestro_vial_con_lesionado': 'siniestro_con_lesionado',
                    'siniestro_vial_sin_lesionado': 'siniestro_sin_lesionado',
                }
                extra_kwargs['subtipo_rescate'] = subtipos_map.get(tipo_reporte, tipo_reporte.replace('rescate_', ''))
                # Si el formulario envía el detalle estructurado de los vehículos,
                # se serializa. Si no, se conserva el texto libre del campo.
                vehiculos_lista = _parsear_vehiculos_involucrados()
                if vehiculos_lista:
                    extra_kwargs['vehiculos_involucrados_json'] = json.dumps(vehiculos_lista, ensure_ascii=False)
            # Subtipo para rescate especializado
            if tipo_reporte.startswith('rescate_') and not tipo_reporte.startswith('rescate_colision_') and not tipo_reporte.startswith('rescate_volcamiento_'):
                subtipos_map = {
                    'rescate_ascensor': 'ascensor', 'rescate_inmueble': 'inmueble',
                    'rescate_tapiada': 'tapiada', 'rescate_golpeada': 'golpeada',
                    'rescate_caida': 'caida', 'rescate_cadaver': 'cadaver',
                }
                extra_kwargs['subtipo_rescate'] = subtipos_map.get(tipo_reporte, tipo_reporte.replace('rescate_', ''))

            # 5. INSTANCIAR EL REPORTE POLIMÓRFICO
            # Se combinan ambos diccionarios para que ningún campo se pase dos
            # veces como argumento (los subtipos y datos calculados ganan).
            parametros = {**specific_kwargs, **extra_kwargs}

            reporte_inst = model_class(
                nro_control=nro_control,
                **cabecera,
                solicitante_nombre=solicitante_nombre,
                solicitante_cedula=solicitante_cedula,
                solicitante_telefono=solicitante_telefono,
                receptor_cedula=receptor_cedula,
                punto_referencia=punto_referencia,
                creador_id=current_user.id,
                estado='Enviado',
                observaciones_generales=observaciones_generales,
                **parametros
            )

            db.session.add(reporte_inst)
            db.session.flush()

            # 6. REGISTRAR PERSONAS AFECTADAS / LESIONADOS (APH y Rescates)
            if (tipo_reporte.startswith('aph_') or tipo_reporte.startswith('rescate_')
                    or tipo_reporte.startswith('siniestro_vial') or tipo_reporte == 'busqueda_rescate'):
                pa_nombres = request.form.getlist('pa_nombre[]')
                pa_cedulas = request.form.getlist('pa_cedula[]')
                pa_edades = request.form.getlist('pa_edad[]')
                pa_sexos = request.form.getlist('pa_sexo[]')
                pa_lesiones = request.form.getlist('pa_lesion[]')
                pa_residencias = request.form.getlist('pa_residencia[]')

                for i, nombre in enumerate(pa_nombres):
                    nombre = (nombre or '').strip()
                    if not nombre:
                        continue
                    persona = ReportePersonaAfectada(
                        reporte_id=reporte_inst.id,
                        nombre_apellido=nombre,
                        cedula_pasaporte=(pa_cedulas[i] if i < len(pa_cedulas) else '').strip() or None,
                        edad=_a_entero(pa_edades[i]) if i < len(pa_edades) else None,
                        sexo=(pa_sexos[i] if i < len(pa_sexos) else '').strip() or None,
                        lesion=(pa_lesiones[i] if i < len(pa_lesiones) else '').strip() or None,
                        residencia=(pa_residencias[i] if i < len(pa_residencias) else '').strip() or None,
                    )
                    db.session.add(persona)

            # 7. REGISTRAR VEHÍCULOS ACTUANTES
            if incluye_secciones_operativas:
                vehiculos_ids = request.form.getlist('vehiculos_actuantes[]')
                conductores = request.form.getlist('conductores[]')
                kms_salida = request.form.getlist('kms_salida[]')
                kms_llegada = request.form.getlist('kms_llegada[]')
                horas_salida_vehiculo = request.form.getlist('horas_salida_vehiculo[]')

                for i, vehiculo_id in enumerate(vehiculos_ids):
                    if not vehiculo_id:
                        continue

                    hora_salida_vehiculo = None
                    valor_hora = (horas_salida_vehiculo[i] if i < len(horas_salida_vehiculo) else '').strip()
                    if valor_hora:
                        try:
                            hora_salida_vehiculo = _parsear_hora(valor_hora)
                        except ValueError:
                            raise ValueError(
                                f'La hora de salida del vehículo actuante N° {i + 1} no es válida '
                                '(formato militar HH:MM:SS, de 00:00:00 a 23:59:59).'
                            )

                    vehiculo_act = ReporteVehiculoActuante(
                        reporte_id=reporte_inst.id,
                        vehiculo_id=int(vehiculo_id),
                        conductor_nombre=(conductores[i] if i < len(conductores) else '') or 'No especificado',
                        km_salida=parse_field_value('capacidad_tanque_litros', kms_salida[i]) if i < len(kms_salida) else 0.0,
                        km_llegada=parse_field_value('capacidad_tanque_litros', kms_llegada[i]) if i < len(kms_llegada) else 0.0,
                        hora_salida=hora_salida_vehiculo,
                    )
                    db.session.add(vehiculo_act)

            # 8. REGISTRAR PERSONAL ACTUANTE
            # "Reporte Elaborado Por" se registra siempre (firma del documento);
            # jefe de comisión, conductor y combatientes solo cuando el tipo de
            # reporte incluye la sección de personal.
            roles_personal = [
                ('Reporte Elaborado Por',
                 f'{current_user.nombre} {current_user.apellido}',
                 current_user.cedula, current_user.rango),
            ]

            if incluye_secciones_operativas:
                jefe_nombre, jefe_ci, jefe_rango = resolver_personal_seleccionado(
                    'jefe_comision_usuario_id', 'jefe_comision_nombre', 'jefe_comision_ci', 'jefe_comision_rango')
                conductor_nombre, conductor_ci, conductor_rango = resolver_personal_seleccionado(
                    'conductor_unidad_usuario_id', 'conductor_unidad_nombre', 'conductor_unidad_ci', 'conductor_unidad_rango')
                roles_personal = [
                    ('Jefe de Comisión', jefe_nombre, jefe_ci, jefe_rango),
                    ('Conductor Unidad', conductor_nombre, conductor_ci, conductor_rango),
                ] + roles_personal

            for rol, nombre, ci, rango in roles_personal:
                if nombre:
                    db.session.add(ReportePersonalActuante(
                        reporte_id=reporte_inst.id,
                        nombre_completo=nombre,
                        cedula=ci,
                        rango=rango,
                        rol_en_servicio=rol
                    ))

            if incluye_secciones_operativas:
                # Combatientes dinámicos (selección de bomberos del sistema o texto manual)
                combatientes_usuario_ids = request.form.getlist('combatientes_usuario_id[]')
                combatientes_nombres = request.form.getlist('combatientes_nombres[]')
                combatientes_cis = request.form.getlist('combatientes_cis[]')
                combatientes_rangos = request.form.getlist('combatientes_rangos[]')

                for i in range(max(len(combatientes_usuario_ids), len(combatientes_nombres))):
                    nombre = ci = rango = None
                    if i < len(combatientes_usuario_ids) and combatientes_usuario_ids[i]:
                        usuario = db.session.get(Usuario, _a_entero(combatientes_usuario_ids[i]))
                        if usuario:
                            nombre, ci, rango = f'{usuario.nombre} {usuario.apellido}', usuario.cedula, usuario.rango
                    if not nombre and i < len(combatientes_nombres) and combatientes_nombres[i]:
                        nombre = combatientes_nombres[i]
                        ci = combatientes_cis[i] if i < len(combatientes_cis) else ''
                        rango = combatientes_rangos[i] if i < len(combatientes_rangos) else ''
                    if nombre:
                        db.session.add(ReportePersonalActuante(
                            reporte_id=reporte_inst.id,
                            nombre_completo=nombre,
                            cedula=ci,
                            rango=rango,
                            rol_en_servicio='Combatiente'
                        ))

                # 9. REGISTRAR ACTUACIÓN DE OTROS ORGANISMOS
                organismos_nombres = request.form.getlist('organismo_nombre[]')
                organismos_jefes = request.form.getlist('organismo_jefe[]')
                organismos_matriculas = request.form.getlist('organismo_matricula[]')
                organismos_cantidades = request.form.getlist('organismo_cantidad[]')

                for i, nombre_organismo in enumerate(organismos_nombres):
                    if not nombre_organismo:
                        continue
                    db.session.add(ReporteOtroOrganismo(
                        reporte_id=reporte_inst.id,
                        nombre_organismo=nombre_organismo,
                        jefe_unidad=organismos_jefes[i] if i < len(organismos_jefes) else '',
                        matricula_unidad=organismos_matriculas[i] if i < len(organismos_matriculas) else '',
                        cantidad_unidades=_a_entero(organismos_cantidades[i]) if i < len(organismos_cantidades) else 1,
                    ))

            db.session.commit()
            flash(f'Reporte {nro_control} creado y enviado con éxito.', 'success')
            return redirect(url_for('reportes.detalle_reporte', reporte_id=reporte_inst.id))

        except ValueError as error:
            # Errores de validación con mensaje apto para el usuario
            db.session.rollback()
            flash(str(error), 'danger')
            return redirect(url_for('reportes.crear_reporte', tipo_reporte=tipo_reporte))
        except IntegrityError:
            db.session.rollback()
            current_app.logger.exception('Conflicto de integridad al crear reporte %s', tipo_reporte)
            flash('No se pudo guardar el reporte: el número de control ya existe. '
                  'Intente guardar nuevamente.', 'danger')
            return redirect(url_for('reportes.crear_reporte', tipo_reporte=tipo_reporte))
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Error al crear reporte %s', tipo_reporte)
            flash('Ocurrió un error al guardar el reporte. Intente nuevamente o contacte al administrador.', 'danger')
            return redirect(url_for('reportes.crear_reporte', tipo_reporte=tipo_reporte))

    vehiculos = Vehiculo.query.filter_by(activo=True).all()
    bomberos = Usuario.query.filter_by(activo=True).order_by(Usuario.rango.asc(), Usuario.nombre.asc()).all()
    date_today = datetime.now().strftime('%Y-%m-%d')
    return render_template(
        'reportes/crear.html',
        tipo_reporte=tipo_reporte,
        title=title,
        vehiculos=vehiculos,
        bomberos=bomberos,
        date_today=date_today,
        incluye_secciones_operativas=incluye_secciones_operativas,
    )


@reportes_bp.route('/detalle/<int:reporte_id>')
@login_required
def detalle_reporte(reporte_id):
    """
    Visualiza el detalle completo de un reporte según su tipo.
    """
    reporte = Reporte.query.get_or_404(reporte_id)
    
    # Restricción: Un bombero ordinario solo puede ver su propio historial de reportes
    if not current_user.es_admin and reporte.creador_id != current_user.id:
        flash('Acceso denegado: No está autorizado para ver este reporte.', 'danger')
        return redirect(url_for('main.index'))
        
    return render_template('reportes/detalle.html', reporte=reporte)


@reportes_bp.route('/pdf/<int:reporte_id>')
@login_required
def descargar_pdf(reporte_id):
    """
    Genera y descarga el reporte operativo en formato PDF (tamaño Carta).

    El logotipo, el nro de control, los tiempos, vehículos, solicitante,
    receptor y dirección se incrustan automáticamente desde la base de datos.
    """
    reporte = Reporte.query.get_or_404(reporte_id)

    # Restricción: Un bombero ordinario solo puede descargar su propio historial
    if not current_user.es_admin and reporte.creador_id != current_user.id:
        flash('Acceso denegado: No está autorizado para descargar este reporte.', 'danger')
        return redirect(url_for('main.index'))

    try:
        pdf_bytes, motor = generar_pdf_reporte(reporte)
    except Exception:
        current_app.logger.exception('Error al generar el PDF del reporte %s', reporte.nro_control)
        flash('No se pudo generar el PDF del reporte. Intente nuevamente.', 'danger')
        return redirect(url_for('reportes.detalle_reporte', reporte_id=reporte.id))

    nombre_archivo = f"Reporte_{reporte.nro_control.replace('/', '_')}.pdf"
    respuesta = Response(pdf_bytes, mimetype='application/pdf')
    respuesta.headers['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return respuesta


@reportes_bp.route('/imprimir/<int:reporte_id>')
@login_required
def imprimir_reporte(reporte_id):
    """
    Vista de impresión/reimpresión del reporte: muestra el documento oficial
    en pantalla para imprimirlo con el navegador (Ctrl+P). Reutiliza la misma
    plantilla del PDF, por lo que el resultado de impresión es idéntico al
    documento descargado. La barra de acciones no se imprime (.no-print).
    """
    reporte = Reporte.query.get_or_404(reporte_id)

    # Restricción: Un bombero ordinario solo puede imprimir su propio historial
    if not current_user.es_admin and reporte.creador_id != current_user.id:
        flash('Acceso denegado: No está autorizado para imprimir este reporte.', 'danger')
        return redirect(url_for('main.index'))

    try:
        return renderizar_html_reporte(reporte)
    except Exception:
        current_app.logger.exception('Error al preparar la impresión del reporte %s', reporte.nro_control)
        flash('No se pudo preparar la impresión del reporte. Intente nuevamente.', 'danger')
        return redirect(url_for('reportes.detalle_reporte', reporte_id=reporte.id))
