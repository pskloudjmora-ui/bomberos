from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from datetime import datetime
import json
from app.models import (
    db, Usuario, Vehiculo, Reporte, ReporteVehiculoActuante, ReportePersonalActuante, ReporteOtroOrganismo,
    ReporteMatpelGLP, ReporteMatpelCombustible, ReporteMatpelQuimico, ReporteMatpelOtros,
    ReportePreHospitalario, ReporteServicioAgua, ReporteServicioInsectos, ReporteServicioAnimal,
    ReporteServicioAchicamiento, ReporteServicioBaldeo,
    ReporteAPHTraslado, ReporteAPHNoTraslado, ReporteAPHInterhospitalario, ReporteAPHSinTraslado,
    ReporteIncendio, ReporteRescateColision, ReporteRescateEspecializado, ReportePersonaAfectada
)
from app.services.pdf_service import generar_pdf_reporte, renderizar_html_reporte

reportes_bp = Blueprint('reportes', __name__)

# Mapeo de tipo_reporte con su clase de modelo SQLAlchemy correspondiente
REPORT_MODEL_MAP = {
    'matpel_glp': ReporteMatpelGLP,
    'matpel_combustible': ReporteMatpelCombustible,
    'matpel_quimico': ReporteMatpelQuimico,
    'matpel_otros': ReporteMatpelOtros,
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
    'rescate_altura': ReporteRescateEspecializado,
    'rescate_tapiada': ReporteRescateEspecializado,
    'rescate_golpeada': ReporteRescateEspecializado,
    'rescate_caida': ReporteRescateEspecializado,
}

# Prefijos correspondientes para la autogeneración del N° de Control
REPORT_PREFIX_MAP = {
    'matpel_glp': 'GLP',
    'matpel_combustible': 'COMB',
    'matpel_quimico': 'QUIM',
    'matpel_otros': 'MAT_OTH',
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
    'rescate_altura': 'RES_ALT',
    'rescate_tapiada': 'RES_TAP',
    'rescate_golpeada': 'RES_GOL',
    'rescate_caida': 'RES_CAID',
}

# Títulos de cabecera legibles para la plantilla crear.html
REPORT_TITLE_MAP = {
    'matpel_glp': 'Reporte MATPEL - Control de Escape de GLP',
    'matpel_combustible': 'Reporte MATPEL - Derrame de Combustible',
    'matpel_quimico': 'Reporte MATPEL - Derrame de Sustancia Química',
    'matpel_otros': 'Reporte MATPEL - Otras Sustancias Peligrosas',
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
    'rescate_altura': 'Rescate de Persona en Altura',
    'rescate_tapiada': 'Rescate de Persona Tapiada',
    'rescate_golpeada': 'Rescate de Persona Golpeada por',
    'rescate_caida': 'Rescate de Persona Caída en',
}

# Campos específicos que corresponden a cada clase de reporte
REPORT_FIELDS_MAP = {
    'matpel_glp': [
        'clasificacion_servicio', 'nombre_producto', 'un_numero', 'riesgo_producto', 'tipo_almacenamiento',
        'certificado_bomberil', 'nro_certificado', 'propietario_nombre', 'propietario_rif_ci',
        'empresa_distribuidora', 'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color',
        'vehiculo_afecto', 'hoja_seguridad', 'extintor', 'equipo_derrame'
    ],
    'matpel_combustible': [
        'tipo_combustible', 'tipo_almacenamiento', 'un_numero', 'capacidad_tanque_litros',
        'vehiculos_involucrados', 'mitigacion_efectuada', 'cantidad_estimada_derrame',
        'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color', 'vehiculo_afecto'
    ],
    'matpel_quimico': [
        'nombre_sustancia', 'un_numero', 'riesgos_especificos',
        'materiales_absorbentes_usados', 'materiales_neutralizantes_usados', 'acciones_mitigacion',
        'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color', 'vehiculo_afecto'
    ],
    'matpel_otros': [
        'descripcion_sustancia', 'riesgos_identificados', 'medidas_seguridad_adoptadas'
    ],
    'pre_hospitalario': [
        'paciente_nombre', 'paciente_edad', 'paciente_genero', 'paciente_cedula',
        'condicion_paciente', 'signos_vitales_tension', 'signos_vitales_pulso',
        'signos_vitales_fr', 'centro_traslado', 'material_medico_utilizado', 'recomendaciones'
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
        'signos_vitales_pa', 'signos_vitales_fc', 'signos_vitales_fr', 'signos_vitales_temperatura',
        'glasgow_apertura_ocular', 'glasgow_respuesta_verbal', 'glasgow_respuesta_motora', 'glasgow_total',
        'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_miembro_superior_d',
        'regla_9_miembro_superior_i', 'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i', 'regla_9_total',
        'procedimiento_paraclinico', 'medicinas_usadas', 'material_medico_usado',
        'centro_hospitalario', 'medico_recibe', 'medico_cedula', 'medico_msds', 'medico_firma',
        'rechazo_nombre', 'rechazo_cedula', 'rechazo_firma'
    ],
    'aph_no_traslado': [
        'signos_vitales_pa', 'signos_vitales_fc', 'signos_vitales_fr', 'signos_vitales_temperatura',
        'glasgow_apertura_ocular', 'glasgow_respuesta_verbal', 'glasgow_respuesta_motora', 'glasgow_total',
        'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_miembro_superior_d',
        'regla_9_miembro_superior_i', 'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i', 'regla_9_total',
        'procedimiento_paraclinico', 'medicinas_usadas', 'material_medico_usado',
        'centro_hospitalario', 'medico_recibe', 'medico_cedula', 'medico_msds', 'medico_firma',
        'motivo_no_traslado', 'indicaciones_dejadas',
        'rechazo_nombre', 'rechazo_cedula', 'rechazo_firma'
    ],
    'aph_interhospitalario': [
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
        'signos_vitales_pa', 'signos_vitales_fc', 'signos_vitales_fr', 'signos_vitales_temperatura',
        'glasgow_apertura_ocular', 'glasgow_respuesta_verbal', 'glasgow_respuesta_motora', 'glasgow_total',
        'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen', 'regla_9_miembro_superior_d',
        'regla_9_miembro_superior_i', 'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i', 'regla_9_total',
        'procedimiento_paraclinico', 'medicinas_usadas', 'material_medico_usado',
        'conducta_adoptada', 'indicaciones_dejadas',
        'rechazo_nombre', 'rechazo_cedula', 'rechazo_firma'
    ],
    'incendio_estructura': [
        'subtipo_incendio', 'clase_incendio', 'intensidad', 'lugar_desarrollo', 'presunto_punto_origen',
        'tipo_equipo_contra_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'evaluacion_preliminar',
        'inmueble_propietario_nombre', 'inmueble_propietario_cedula', 'inmueble_propietario_telefono'
    ],
    'incendio_apoyo': [
        'subtipo_incendio', 'clase_incendio', 'intensidad', 'lugar_desarrollo', 'presunto_punto_origen',
        'tipo_equipo_contra_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'evaluacion_preliminar'
    ],
    'incendio_electrico': [
        'subtipo_incendio', 'clase_incendio', 'intensidad', 'lugar_desarrollo', 'presunto_punto_origen',
        'tipo_equipo_contra_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'evaluacion_preliminar'
    ],
    'incendio_vehiculo': [
        'subtipo_incendio', 'clase_incendio', 'intensidad', 'lugar_desarrollo', 'presunto_punto_origen',
        'tipo_equipo_contra_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'evaluacion_preliminar',
        'vehiculo_marca', 'vehiculo_modelo', 'vehiculo_placa', 'vehiculo_color',
        'vehiculo_anio', 'vehiculo_tipo',
        'propietario_nombre', 'propietario_cedula', 'propietario_edad', 'propietario_telefono'
    ],
    'incendio_desechos': [
        'subtipo_incendio', 'clase_incendio', 'intensidad', 'lugar_desarrollo', 'presunto_punto_origen',
        'tipo_equipo_contra_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'evaluacion_preliminar'
    ],
    'incendio_vegetacion': [
        'subtipo_incendio', 'tipo_incendio', 'clase_incendio', 'intensidad',
        'lugar_desarrollo', 'presunto_punto_origen',
        'tipo_equipo_contra_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'evaluacion_preliminar',
        'tipo_terreno', 'tipo_vegetacion', 'extension_terreno', 'extension_terreno_afectada', 'coordenadas'
    ],
    'incendio_arbol': [
        'subtipo_incendio', 'clase_incendio', 'intensidad',
        'lugar_desarrollo', 'presunto_punto_origen',
        'tipo_equipo_contra_incendio', 'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'evaluacion_preliminar',
        'tipo_terreno', 'tipo_vegetacion', 'extension_terreno', 'extension_terreno_afectada', 'coordenadas'
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
        'subtipo_rescate', 'tipo_servicio',
        'despliegue_vehiculos', 'despliegue_conductor_nombre', 'despliegue_conductor_ci',
        'despliegue_jefe_nombre', 'despliegue_jefe_ci', 'despliegue_cantidad_bomberos', 'despliegue_material_usado'
    ],
    'rescate_inmueble': [
        'subtipo_rescate', 'tipo_servicio',
        'despliegue_vehiculos', 'despliegue_conductor_nombre', 'despliegue_conductor_ci',
        'despliegue_jefe_nombre', 'despliegue_jefe_ci', 'despliegue_cantidad_bomberos', 'despliegue_material_usado'
    ],
    'rescate_altura': [
        'subtipo_rescate', 'tipo_servicio',
        'despliegue_vehiculos', 'despliegue_conductor_nombre', 'despliegue_conductor_ci',
        'despliegue_jefe_nombre', 'despliegue_jefe_ci', 'despliegue_cantidad_bomberos', 'despliegue_material_usado'
    ],
    'rescate_tapiada': [
        'subtipo_rescate', 'tipo_servicio',
        'despliegue_vehiculos', 'despliegue_conductor_nombre', 'despliegue_conductor_ci',
        'despliegue_jefe_nombre', 'despliegue_jefe_ci', 'despliegue_cantidad_bomberos', 'despliegue_material_usado'
    ],
    'rescate_golpeada': [
        'subtipo_rescate', 'tipo_servicio',
        'despliegue_vehiculos', 'despliegue_conductor_nombre', 'despliegue_conductor_ci',
        'despliegue_jefe_nombre', 'despliegue_jefe_ci', 'despliegue_cantidad_bomberos', 'despliegue_material_usado'
    ],
    'rescate_caida': [
        'subtipo_rescate', 'tipo_servicio',
        'despliegue_vehiculos', 'despliegue_conductor_nombre', 'despliegue_conductor_ci',
        'despliegue_jefe_nombre', 'despliegue_jefe_ci', 'despliegue_cantidad_bomberos', 'despliegue_material_usado'
    ],
}

def resolver_personal_seleccionado(clave_usuario_id, clave_nombre, clave_ci, clave_rango):
    """
    Resuelve los datos de un bombero del formulario: si se eligió un usuario
    del listado (select), toma nombre, cédula y rango desde la BD; en caso
    contrario usa los campos de texto manuales (compatibilidad).
    Devuelve (nombre_completo, cedula, rango).
    """
    usuario_id = request.form.get(clave_usuario_id)
    if usuario_id:
        usuario = Usuario.query.get(int(usuario_id))
        if usuario:
            return f'{usuario.nombre} {usuario.apellido}', usuario.cedula, usuario.rango
    return request.form.get(clave_nombre), request.form.get(clave_ci), request.form.get(clave_rango)


def parse_field_value(field_name, raw_val):
    """
    Parsea los valores raw provenientes del formulario de acuerdo a sus tipos de datos requeridos en la BD.
    """
    if raw_val is None or raw_val == '':
        return None
    # Booleanos
    if field_name in ['certificado_bomberil', 'hoja_seguridad', 'extintor', 'equipo_derrame', 'limpieza_vias_efectuada', 'vehiculo_afecto',
                       'medico_firma', 'rechazo_firma', 'hubo_propagacion', 'poseia_equipos', 'fue_usado']:
        return raw_val in ['Si', 'on', 'true', '1', True]
    # Enteros
    if field_name in ['paciente_edad', 'signos_vitales_pulso', 'signos_vitales_fr', 'litros_distribuidos',
                       'beneficiarios_estimados', 'litros_agua_utilizados',
                       'signos_vitales_fc', 'signos_vitales_fr', 'glasgow_apertura_ocular',
                       'glasgow_respuesta_verbal', 'glasgow_respuesta_motora', 'glasgow_total',
                       'regla_9_total', 'propietario_edad', 'despliegue_cantidad_bomberos']:
        try:
            return int(raw_val)
        except ValueError:
            return 0
    # Flotantes / Decimales
    if field_name in ['cantidad_estimada_derrame', 'capacidad_tanque_litros',
                       'regla_9_cabeza', 'regla_9_torax', 'regla_9_abdomen',
                       'regla_9_miembro_superior_d', 'regla_9_miembro_superior_i',
                       'regla_9_miembro_inferior_d', 'regla_9_miembro_inferior_i',
                       'porcentaje_perdida_fuego', 'porcentaje_perdida_humo', 'porcentaje_perdida_total']:
        try:
            return float(raw_val)
        except ValueError:
            return 0.0
    return raw_val


@reportes_bp.route('/crear/<tipo_reporte>', methods=['GET', 'POST'])
@login_required
def crear_reporte(tipo_reporte):
    """
    Controlador dinámico unificado que procesa la creación de los 10 tipos de reportes de actuación.
    """
    if tipo_reporte not in REPORT_MODEL_MAP:
        flash('Tipo de reporte no válido.', 'danger')
        return redirect(url_for('main.index'))

    model_class = REPORT_MODEL_MAP[tipo_reporte]
    prefix = REPORT_PREFIX_MAP[tipo_reporte]
    title = REPORT_TITLE_MAP[tipo_reporte]
    fields = REPORT_FIELDS_MAP[tipo_reporte]

    if request.method == 'POST':
        try:
            # 1. AUTOGENERAR N° DE CONTROL SECUENCIAL ÚNICO
            año_actual = datetime.utcnow().year
            conteo_año = Reporte.query.filter(
                db.extract('year', Reporte.fecha) == año_actual,
                Reporte.tipo_reporte == tipo_reporte
            ).count()
            nro_control = f"{prefix}-{año_actual}-{str(conteo_año + 1).zfill(4)}"

            # 2. CAPTURAR DATOS COMUNES DE CABECERA
            fecha_str = request.form.get('fecha')
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else datetime.utcnow().date()
            
            hora_aviso = datetime.strptime(request.form.get('hora_aviso'), '%H:%M').time()
            hora_salida = datetime.strptime(request.form.get('hora_salida'), '%H:%M').time()
            hora_llegada = datetime.strptime(request.form.get('hora_llegada'), '%H:%M').time()
            hora_regreso = datetime.strptime(request.form.get('hora_regreso'), '%H:%M').time()

            solicitante_nombre = request.form.get('solicitante_nombre')
            solicitante_cedula = request.form.get('solicitante_cedula')
            solicitante_telefono = request.form.get('solicitante_telefono')
            receptor_aviso = request.form.get('receptor_aviso')
            receptor_cedula = request.form.get('receptor_cedula')
            
            direccion = request.form.get('direccion')
            punto_referencia = request.form.get('punto_referencia')
            observaciones_generales = request.form.get('observaciones_generales')

            # 3. EXTRAER Y PARSEAR CAMPOS ESPECÍFICOS DE LA SUBCLASE
            specific_kwargs = {}
            for field in fields:
                raw_val = request.form.get(field)
                # Si el campo tiene opción "Otro", usar el valor del input de texto
                if raw_val == 'Otro':
                    otro_val = request.form.get(f'{field}_otro')
                    if otro_val:
                        raw_val = otro_val
                specific_kwargs[field] = parse_field_value(field, raw_val)

            # 4. INSTANCIAR Y GUARDAR REPORTE POLIMÓRFICO
            extra_kwargs = {}
            # Subtipo para incendios
            if tipo_reporte.startswith('incendio_'):
                subtipos_map = {
                    'incendio_estructura': 'estructura', 'incendio_apoyo': 'apoyo',
                    'incendio_electrico': 'electrico', 'incendio_vehiculo': 'vehiculo',
                    'incendio_desechos': 'desechos', 'incendio_vegetacion': 'vegetacion',
                    'incendio_arbol': 'arbol',
                }
                extra_kwargs['subtipo_incendio'] = subtipos_map.get(tipo_reporte, tipo_reporte.replace('incendio_', ''))
            # Subtipo para rescate colisión/volcamiento
            if tipo_reporte.startswith('rescate_colision_') or tipo_reporte.startswith('rescate_volcamiento_'):
                subtipos_map = {
                    'rescate_colision_con_lesionado': 'colision_con_lesionado',
                    'rescate_colision_sin_lesionado': 'colision_sin_lesionado',
                    'rescate_volcamiento_con_lesionado': 'volcamiento_con_lesionado',
                    'rescate_volcamiento_sin_lesionado': 'volcamiento_sin_lesionado',
                }
                extra_kwargs['subtipo_rescate'] = subtipos_map.get(tipo_reporte, tipo_reporte.replace('rescate_', ''))
                # Serializar vehículos involucrados
                veh_inv_marca = request.form.getlist('veh_inv_marca[]')
                veh_inv_modelo = request.form.getlist('veh_inv_modelo[]')
                veh_inv_placa = request.form.getlist('veh_inv_placa[]')
                veh_inv_color = request.form.getlist('veh_inv_color[]')
                veh_inv_anio = request.form.getlist('veh_inv_anio[]')
                veh_inv_tipo = request.form.getlist('veh_inv_tipo[]')
                veh_inv_propietario = request.form.getlist('veh_inv_propietario[]')
                veh_inv_cedula = request.form.getlist('veh_inv_cedula[]')
                veh_inv_telefono = request.form.getlist('veh_inv_telefono[]')
                vehiculos_lista = []
                for i in range(max(len(veh_inv_marca), len(veh_inv_placa))):
                    vehiculos_lista.append({
                        'marca': veh_inv_marca[i] if i < len(veh_inv_marca) else '',
                        'modelo': veh_inv_modelo[i] if i < len(veh_inv_modelo) else '',
                        'placa': veh_inv_placa[i] if i < len(veh_inv_placa) else '',
                        'color': veh_inv_color[i] if i < len(veh_inv_color) else '',
                        'anio': veh_inv_anio[i] if i < len(veh_inv_anio) else '',
                        'tipo': veh_inv_tipo[i] if i < len(veh_inv_tipo) else '',
                        'propietario': veh_inv_propietario[i] if i < len(veh_inv_propietario) else '',
                        'cedula': veh_inv_cedula[i] if i < len(veh_inv_cedula) else '',
                        'telefono': veh_inv_telefono[i] if i < len(veh_inv_telefono) else '',
                    })
                extra_kwargs['vehiculos_involucrados_json'] = json.dumps(vehiculos_lista) if vehiculos_lista else None
            # Subtipo para rescate especializado
            if tipo_reporte.startswith('rescate_') and not tipo_reporte.startswith('rescate_colision_') and not tipo_reporte.startswith('rescate_volcamiento_'):
                subtipos_map = {
                    'rescate_ascensor': 'ascensor', 'rescate_inmueble': 'inmueble',
                    'rescate_altura': 'altura', 'rescate_tapiada': 'tapiada',
                    'rescate_golpeada': 'golpeada', 'rescate_caida': 'caida',
                }
                extra_kwargs['subtipo_rescate'] = subtipos_map.get(tipo_reporte, tipo_reporte.replace('rescate_', ''))

            reporte_inst = model_class(
                nro_control=nro_control,
                fecha=fecha,
                clase_aviso=request.form.get('clase_aviso', 'Radial'),
                hora_aviso=hora_aviso,
                hora_salida=hora_salida,
                hora_llegada=hora_llegada,
                hora_regreso=hora_regreso,
                solicitante_nombre=solicitante_nombre,
                solicitante_cedula=solicitante_cedula,
                solicitante_telefono=solicitante_telefono,
                receptor_aviso=receptor_aviso,
                receptor_cedula=receptor_cedula,
                direccion=direccion,
                punto_referencia=punto_referencia,
                creador_id=current_user.id,
                estado='Enviado',
                observaciones_generales=observaciones_generales,
                **specific_kwargs,
                **extra_kwargs
            )
            
            db.session.add(reporte_inst)
            db.session.flush()

            # 5. REGISTRAR PERSONAS AFECTADAS (para APH y Rescates)
            if tipo_reporte.startswith('aph_') or tipo_reporte.startswith('rescate_'):
                pa_nombres = request.form.getlist('pa_nombre[]')
                pa_cedulas = request.form.getlist('pa_cedula[]')
                pa_edades = request.form.getlist('pa_edad[]')
                pa_sexos = request.form.getlist('pa_sexo[]')
                pa_lesiones = request.form.getlist('pa_lesion[]')
                pa_residencias = request.form.getlist('pa_residencia[]')

                for i in range(max(len(pa_nombres), 0)):
                    nombre = pa_nombres[i] if i < len(pa_nombres) else ''
                    if nombre:
                        persona = ReportePersonaAfectada(
                            reporte_id=reporte_inst.id,
                            nombre_apellido=nombre,
                            cedula_pasaporte=pa_cedulas[i] if i < len(pa_cedulas) else '',
                            edad=int(pa_edades[i]) if i < len(pa_edades) and pa_edades[i] else None,
                            sexo=pa_sexos[i] if i < len(pa_sexos) else '',
                            lesion=pa_lesiones[i] if i < len(pa_lesiones) else '',
                            residencia=pa_residencias[i] if i < len(pa_residencias) else '',
                        )
                        db.session.add(persona)

            # 6. REGISTRAR VEHÍCULOS ACTUANTES
            vehiculos_ids = request.form.getlist('vehiculos_actuantes[]')
            conductores = request.form.getlist('conductores[]')
            kms_salida = request.form.getlist('kms_salida[]')
            kms_llegada = request.form.getlist('kms_llegada[]')
            
            for i in range(len(vehiculos_ids)):
                if vehiculos_ids[i]:
                    vehiculo_act = ReporteVehiculoActuante(
                        reporte_id=reporte_inst.id,
                        vehiculo_id=int(vehiculos_ids[i]),
                        conductor_nombre=conductores[i] if i < len(conductores) else "No especificado",
                        km_salida=float(kms_salida[i]) if i < len(kms_salida) and kms_salida[i] else 0.0,
                        km_llegada=float(kms_llegada[i]) if i < len(kms_llegada) and kms_llegada[i] else 0.0
                    )
                    db.session.add(vehiculo_act)

            # 7. REGISTRAR PERSONAL ACTUANTE (Jefe de Comisión, Conductor y Elaborado Por)
            jefe_nombre, jefe_ci, jefe_rango = resolver_personal_seleccionado(
                'jefe_comision_usuario_id', 'jefe_comision_nombre', 'jefe_comision_ci', 'jefe_comision_rango')
            conductor_nombre, conductor_ci, conductor_rango = resolver_personal_seleccionado(
                'conductor_unidad_usuario_id', 'conductor_unidad_nombre', 'conductor_unidad_ci', 'conductor_unidad_rango')

            roles_personal = [
                ('Jefe de Comisión', jefe_nombre, jefe_ci, jefe_rango),
                ('Conductor Unidad', conductor_nombre, conductor_ci, conductor_rango),
                ('Reporte Elaborado Por', current_user.nombre + " " + current_user.apellido, current_user.cedula, current_user.rango)
            ]
            
            for rol, nombre, ci, rango in roles_personal:
                if nombre:
                    pers_act = ReportePersonalActuante(
                        reporte_id=reporte_inst.id,
                        nombre_completo=nombre,
                        cedula=ci,
                        rango=rango,
                        rol_en_servicio=rol
                    )
                    db.session.add(pers_act)

            # Combatientes dinámicos (selección de bomberos del sistema o texto manual)
            combatientes_usuario_ids = request.form.getlist('combatientes_usuario_id[]')
            combatientes_nombres = request.form.getlist('combatientes_nombres[]')
            combatientes_cis = request.form.getlist('combatientes_cis[]')
            combatientes_rangos = request.form.getlist('combatientes_rangos[]')
            
            for i in range(max(len(combatientes_usuario_ids), len(combatientes_nombres))):
                nombre = ci = rango = None
                if i < len(combatientes_usuario_ids) and combatientes_usuario_ids[i]:
                    usuario = Usuario.query.get(int(combatientes_usuario_ids[i]))
                    if usuario:
                        nombre, ci, rango = f'{usuario.nombre} {usuario.apellido}', usuario.cedula, usuario.rango
                if not nombre and i < len(combatientes_nombres) and combatientes_nombres[i]:
                    nombre = combatientes_nombres[i]
                    ci = combatientes_cis[i] if i < len(combatientes_cis) else ""
                    rango = combatientes_rangos[i] if i < len(combatientes_rangos) else ""
                if nombre:
                    pers_act = ReportePersonalActuante(
                        reporte_id=reporte_inst.id,
                        nombre_completo=nombre,
                        cedula=ci,
                        rango=rango,
                        rol_en_servicio='Combatiente'
                    )
                    db.session.add(pers_act)

            # 8. REGISTRAR ACTUACIÓN DE OTROS ORGANISMOS
            organismos_nombres = request.form.getlist('organismo_nombre[]')
            organismos_jefes = request.form.getlist('organismo_jefe[]')
            organismos_matriculas = request.form.getlist('organismo_matricula[]')
            organismos_cantidades = request.form.getlist('organismo_cantidad[]')
            
            for i in range(len(organismos_nombres)):
                if organismos_nombres[i]:
                    org_act = ReporteOtroOrganismo(
                        reporte_id=reporte_inst.id,
                        nombre_organismo=organismos_nombres[i],
                        jefe_unidad=organismos_jefes[i] if i < len(organismos_jefes) else "",
                        matricula_unidad=organismos_matriculas[i] if i < len(organismos_matriculas) else "",
                        cantidad_unidades=int(organismos_cantidades[i]) if i < len(organismos_cantidades) and organismos_cantidades[i] else 1
                    )
                    db.session.add(org_act)

            db.session.commit()
            flash(f'Reporte {nro_control} creado y enviado con éxito.', 'success')
            return redirect(url_for('reportes.detalle_reporte', reporte_id=reporte_inst.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el reporte: {str(e)}', 'danger')
            return redirect(url_for('reportes.crear_reporte', tipo_reporte=tipo_reporte))

    vehiculos = Vehiculo.query.filter_by(activo=True).all()
    bomberos = Usuario.query.filter_by(activo=True).order_by(Usuario.rango.asc(), Usuario.nombre.asc()).all()
    date_today = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template(
        'reportes/crear.html',
        tipo_reporte=tipo_reporte,
        title=title,
        vehiculos=vehiculos,
        bomberos=bomberos,
        date_today=date_today
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
    except Exception as e:
        flash(f'Error al generar el PDF: {str(e)}', 'danger')
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
    except Exception as e:
        flash(f'Error al preparar la impresión: {str(e)}', 'danger')
        return redirect(url_for('reportes.detalle_reporte', reporte_id=reporte.id))
