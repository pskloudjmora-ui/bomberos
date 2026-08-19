from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from datetime import datetime
from app.models import (
    db, Usuario, Vehiculo, Reporte, ReporteVehiculoActuante, ReportePersonalActuante, ReporteOtroOrganismo,
    ReporteMatpelGLP, ReporteMatpelCombustible, ReporteMatpelQuimico, ReporteMatpelOtros,
    ReportePreHospitalario, ReporteServicioAgua, ReporteServicioInsectos, ReporteServicioAnimal,
    ReporteServicioAchicamiento, ReporteServicioBaldeo
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
}

# Títulos de cabecera legibles para la plantilla crear.html
REPORT_TITLE_MAP = {
    'matpel_glp': 'Reporte MATPEL - Control de Escape de GLP',
    'matpel_combustible': 'Reporte MATPEL - Derrame de Combustible',
    'matpel_quimico': 'Reporte MATPEL - Derrame de Sustancia Química',
    'matpel_otros': 'Reporte MATPEL - Otras Sustancias Peligrosas',
    'pre_hospitalario': 'Atención Pre-Hospitalaria / Traslado de Emergencia',
    'servicio_agua': 'Servicio Especial - Abastecimiento de Agua',
    'servicio_insectos': 'Servicio Especial - Control y Re-ubicación de Insectos',
    'servicio_animal': 'Servicio Especial - Control de Animal Doméstico',
    'servicio_achicamiento': 'Servicio Especial - Achicamiento por Aguas Estancadas',
    'servicio_baldeo': 'Servicio Especial - Baldeo de Agua',
}

# Campos específicos que corresponden a cada clase de reporte
REPORT_FIELDS_MAP = {
    'matpel_glp': [
        'clasificacion_servicio', 'nombre_producto', 'un_numero', 'riesgo_producto', 'tipo_almacenamiento',
        'certificado_bomberil', 'nro_certificado', 'propietario_nombre', 'propietario_rif_ci',
        'empresa_distribuidora', 'vehiculo_marca', 'vehiculo_placa', 'vehiculo_color',
        'hoja_seguridad', 'extintor', 'equipo_derrame'
    ],
    'matpel_combustible': [
        'tipo_combustible', 'tipo_almacenamiento', 'vehiculos_involucrados',
        'mitigacion_efectuada', 'cantidad_estimada_derrame'
    ],
    'matpel_quimico': [
        'nombre_sustancia', 'un_numero', 'riesgos_especificos',
        'materiales_absorbentes_usados', 'materiales_neutralizantes_usados', 'acciones_mitigacion'
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
    ]
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
    if field_name in ['certificado_bomberil', 'hoja_seguridad', 'extintor', 'equipo_derrame', 'limpieza_vias_efectuada']:
        return raw_val in ['Si', 'on', 'true', '1', True]
    # Enteros
    if field_name in ['paciente_edad', 'signos_vitales_pulso', 'signos_vitales_fr', 'litros_distribuidos', 'beneficiarios_estimados', 'litros_agua_utilizados']:
        try:
            return int(raw_val)
        except ValueError:
            return 0
    # Flotantes / Decimales
    if field_name in ['cantidad_estimada_derrame']:
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
            
            direccion = request.form.get('direccion')
            punto_referencia = request.form.get('punto_referencia')
            observaciones_generales = request.form.get('observaciones_generales')

            # 3. EXTRAER Y PARSEAR CAMPOS ESPECÍFICOS DE LA SUBCLASE
            specific_kwargs = {}
            for field in fields:
                raw_val = request.form.get(field)
                specific_kwargs[field] = parse_field_value(field, raw_val)

            # 4. INSTANCIAR Y GUARDAR REPORTE POLIMÓRFICO
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
                direccion=direccion,
                punto_referencia=punto_referencia,
                creador_id=current_user.id,
                estado='Enviado',
                observaciones_generales=observaciones_generales,
                **specific_kwargs
            )
            
            db.session.add(reporte_inst)
            db.session.flush()

            # 5. REGISTRAR VEHÍCULOS ACTUANTES
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

            # 6. REGISTRAR PERSONAL ACTUANTE (Jefe de Comisión, Conductor y Elaborado Por)
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

            # 7. REGISTRAR ACTUACIÓN DE OTROS ORGANISMOS
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
