from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, extract, or_, case
from datetime import datetime, timedelta, time
from app.models import (
    db, Usuario, Vehiculo, Reporte, 
    ReporteMatpelGLP, ReporteServicioAgua, ReporteServicioBaldeo,
    RANGOS_BOMBERILES
)
from app.services.pdf_service import obtener_logo_data_uri

main_bp = Blueprint('main', __name__)

def _orden_jerarquia(column):
    """
    Expresión SQL para ordenar por la jerarquía establecida en RANGOS_BOMBERILES
    (los rangos no incluidos en la lista van al final, ordenados alfabéticamente).
    """
    rango_pos = case(
        {rango: posicion for posicion, rango in enumerate(RANGOS_BOMBERILES)},
        value=column,
        else_=len(RANGOS_BOMBERILES)
    )
    return rango_pos

def _aplicar_filtros_usuarios(args):
    """
    Aplica los filtros de búsqueda de la gestión de personal: texto libre,
    rango jerárquico, rol del sistema y estado de la cuenta.
    Devuelve (consulta, dict_filtros).
    """
    query = Usuario.query

    texto = args.get('q', '').strip()
    rango = args.get('rango', '').strip()
    rol = args.get('rol', '').strip()
    estado = args.get('estado', '').strip()

    if texto:
        patron = f'%{texto}%'
        query = query.filter(or_(
            Usuario.nombre.ilike(patron),
            Usuario.apellido.ilike(patron),
            Usuario.username.ilike(patron),
            Usuario.cedula.ilike(patron)
        ))

    if rango:
        query = query.filter(Usuario.rango == rango)

    if rol in ('administrador', 'bombero'):
        query = query.filter(Usuario.rol == rol)

    if estado in ('activo', 'inactivo'):
        query = query.filter(Usuario.activo == (estado == 'activo'))

    filtros = {'q': texto, 'rango': rango, 'rol': rol, 'estado': estado}
    return query, filtros

@main_bp.route('/')
@login_required
def index():
    """
    Página de inicio / Dashboard general. Redirige según el rol.
    """
    if current_user.es_admin:
        return redirect(url_for('main.dashboard_admin'))
    return redirect(url_for('main.historial_bombero'))


@main_bp.route('/historial')
@login_required
def historial_bombero():
    """
    Muestra el historial de reportes creados por el bombero actualmente autenticado.
    """
    # Filtrar reportes del usuario actual
    reportes = Reporte.query.filter_by(creador_id=current_user.id).order_by(Reporte.fecha.desc(), Reporte.hora_aviso.desc()).all()
    return render_template('bombero/historial.html', reportes=reportes)


@main_bp.route('/admin/dashboard')
@login_required
def dashboard_admin():
    """
    Dashboard principal del Administrador.
    Muestra Métricas Clave (KPIs) y datos para los gráficos mediante consultas agregadas.
    Permite filtrar incidencias por rango de fechas, tipo de reporte y vehículo.
    """
    if not current_user.es_admin:
        flash('Acceso denegado: Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('main.index'))

    # 1. OBTENCIÓN DE FILTROS DE BÚSQUEDA
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    tipo_reporte_filtro = request.args.get('tipo_reporte')
    vehiculo_filtro = request.args.get('vehiculo')  # ID o unidad del vehículo

    # Construir consulta base
    query = Reporte.query

    # Aplicar filtros de fecha si se suministran
    if fecha_inicio_str:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        query = query.filter(Reporte.fecha >= fecha_inicio)
    else:
        # Por defecto, últimos 30 días
        fecha_inicio = (datetime.utcnow() - timedelta(days=30)).date()
        query = query.filter(Reporte.fecha >= fecha_inicio)

    if fecha_fin_str:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
        query = query.filter(Reporte.fecha <= fecha_fin)
    else:
        fecha_fin = datetime.utcnow().date()
        query = query.filter(Reporte.fecha <= fecha_fin)

    if tipo_reporte_filtro and tipo_reporte_filtro != 'Todos':
        query = query.filter(Reporte.tipo_reporte == tipo_reporte_filtro)

    if vehiculo_filtro and vehiculo_filtro != 'Todos':
        # Filtrar a través de la relación de vehículos actuantes
        query = query.join(Reporte.vehiculos_actuantes).filter(
            Reporte.vehiculos_actuantes.any(vehiculo_id=vehiculo_filtro)
        )

    # Lista de todos los reportes que cumplen con el filtro para la tabla del panel
    reportes_filtrados = query.order_by(Reporte.fecha.desc()).all()

    # 2. CONSULTAS AGREGADAS (db.session.query) PARA KPIs
    # A. Total de Incidencias en el período filtrado
    total_incidencias = query.count()

    # B. Litros totales de agua distribuidos (Abastecimiento de Agua + Baldeo)
    # Litros en Servicios de Agua (Abastecimiento)
    litros_abastecimiento = db.session.query(func.sum(ReporteServicioAgua.litros_distribuidos))\
        .filter(ReporteServicioAgua.fecha >= fecha_inicio, ReporteServicioAgua.fecha <= fecha_fin).scalar() or 0

    # Litros en Servicios de Baldeo
    litros_baldeo = db.session.query(func.sum(ReporteServicioBaldeo.litros_agua_utilizados))\
        .filter(ReporteServicioBaldeo.fecha >= fecha_inicio, ReporteServicioBaldeo.fecha <= fecha_fin).scalar() or 0

    litros_totales_agua = litros_abastecimiento + litros_baldeo

    # C. Tipo de servicio más frecuente en el período
    tipo_mas_frecuente_query = db.session.query(
        Reporte.tipo_reporte, func.count(Reporte.id).label('total')
    ).filter(Reporte.fecha >= fecha_inicio, Reporte.fecha <= fecha_fin)\
     .group_by(Reporte.tipo_reporte)\
     .order_by(func.count(Reporte.id).desc()).first()
    
    tipo_mas_frecuente = tipo_mas_frecuente_query[0] if tipo_mas_frecuente_query else "Ninguno"
    tipo_mas_frecuente_cant = tipo_mas_frecuente_query[1] if tipo_mas_frecuente_query else 0

    # D. Cálculo de Tiempo Promedio de Respuesta
    # Obtenemos las horas de aviso y llegada del período para promediar en minutos
    tiempos = db.session.query(Reporte.hora_aviso, Reporte.hora_llegada)\
        .filter(Reporte.fecha >= fecha_inicio, Reporte.fecha <= fecha_fin).all()
    
    tiempo_promedio_minutos = 0
    tiempos_validos = 0
    
    for h_aviso, h_llegada in tiempos:
        if h_aviso and h_llegada:
            # Convertir a objetos datetime del mismo día para restar
            dt_aviso = datetime.combine(datetime.min, h_aviso)
            dt_llegada = datetime.combine(datetime.min, h_llegada)
            
            # Manejar el caso de cambio de día si el servicio cruzó la medianoche
            if dt_llegada < dt_aviso:
                dt_llegada += timedelta(days=1)
                
            diff = (dt_llegada - dt_aviso).total_seconds() / 60.0
            tiempo_promedio_minutos += diff
            tiempos_validos += 1
            
    if tiempos_validos > 0:
        tiempo_promedio_minutos = round(tiempo_promedio_minutos / tiempos_validos, 1)

    # 3. DATOS PARA GRÁFICOS DINÁMICOS
    # Desglose de incidencias por tipo (para gráfico circular/barras)
    desglose_tipos = db.session.query(
        Reporte.tipo_reporte, func.count(Reporte.id)
    ).filter(Reporte.fecha >= fecha_inicio, Reporte.fecha <= fecha_fin)\
     .group_by(Reporte.tipo_reporte).all()
     
    datos_grafico_pastel = {t[0]: t[1] for t in desglose_tipos}

    # Desglose de incidencias por fecha (para gráfico de líneas - tendencia)
    desglose_fechas = db.session.query(
        Reporte.fecha, func.count(Reporte.id)
    ).filter(Reporte.fecha >= fecha_inicio, Reporte.fecha <= fecha_fin)\
     .group_by(Reporte.fecha)\
     .order_by(Reporte.fecha.asc()).all()
     
    fechas_grafico = [f[0].strftime('%d/%m') for f in desglose_fechas]
    cantidades_grafico = [f[1] for f in desglose_fechas]

    # Cargar todos los vehículos para el filtro
    vehiculos = Vehiculo.query.filter_by(activo=True).all()

    return render_template(
        'admin/dashboard.html',
        reportes=reportes_filtrados,
        total_incidencias=total_incidencias,
        litros_totales_agua=litros_totales_agua,
        tipo_mas_frecuente=tipo_mas_frecuente,
        tipo_mas_frecuente_cant=tipo_mas_frecuente_cant,
        tiempo_promedio_minutos=tiempo_promedio_minutos,
        datos_pastel=datos_grafico_pastel,
        fechas_grafico=fechas_grafico,
        cantidades_grafico=cantidades_grafico,
        vehiculos=vehiculos,
        filtro_inicio=fecha_inicio_str or fecha_inicio.strftime('%Y-%m-%d'),
        filtro_fin=fecha_fin_str or fecha_fin.strftime('%Y-%m-%d'),
        filtro_tipo=tipo_reporte_filtro or 'Todos',
        filtro_vehiculo=vehiculo_filtro or 'Todos'
    )


@main_bp.route('/admin/usuarios')
@login_required
def gestionar_usuarios():
    """
    Visualiza la lista de usuarios y bomberos registrados con filtros de búsqueda
    (texto, rango, rol y estado). Exclusivo de administrador.
    """
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    query, filtros = _aplicar_filtros_usuarios(request.args)
    usuarios = query.order_by(
        _orden_jerarquia(Usuario.rango).asc(),
        Usuario.nombre.asc()
    ).all()

    return render_template(
        'admin/usuarios.html',
        usuarios=usuarios,
        rangos=RANGOS_BOMBERILES,
        filtros=filtros
    )


@main_bp.route('/admin/usuarios/imprimir')
@login_required
def lista_bomberos_imprimir():
    """
    Vista imprimible (lista oficial) del personal bomberil filtrado por los
    mismos criterios de búsqueda de la gestión. Exclusivo de administrador.
    """
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    query, filtros = _aplicar_filtros_usuarios(request.args)
    usuarios = query.order_by(
        _orden_jerarquia(Usuario.rango).asc(),
        Usuario.nombre.asc()
    ).all()

    fecha_emision = datetime.utcnow().strftime('%d/%m/%Y %H:%M')

    return render_template(
        'admin/lista_bomberos.html',
        usuarios=usuarios,
        filtros=filtros,
        logo=obtener_logo_data_uri(),
        fecha_emision=fecha_emision,
        emitido_por=current_user
    )


@main_bp.route('/admin/usuario/<int:usuario_id>')
@login_required
def ver_usuario(usuario_id):
    """
    Visualiza el detalle completo de un bombero: datos personales, credenciales
    de acceso y reportes que ha elaborado. Exclusivo de administrador.
    """
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))
    usuario = Usuario.query.get_or_404(usuario_id)
    reportes = Reporte.query.filter_by(creador_id=usuario.id).order_by(Reporte.fecha.desc()).all()
    return render_template('admin/ver_usuario.html', usuario=usuario, reportes=reportes)


@main_bp.route('/admin/usuario/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_usuario(usuario_id):
    """
    Edita los datos y credenciales de un bombero. Exclusivo de administrador.
    Si se deja la contraseña en blanco, se conserva la actual.
    """
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    usuario = Usuario.query.get_or_404(usuario_id)

    if request.method == 'POST':
        username = request.form.get('username')
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        cedula = request.form.get('cedula')
        rango = request.form.get('rango')
        rol = request.form.get('rol', 'bombero')
        activo = request.form.get('activo') == 'on'
        password = request.form.get('password')

        # Validación de unicidad (excluyendo al propio usuario)
        duplicado = Usuario.query.filter(
            ((Usuario.username == username) | (Usuario.cedula == cedula)) &
            (Usuario.id != usuario.id)
        ).first()
        if duplicado:
            flash('Error: El nombre de usuario o la cédula ya pertenecen a otro funcionario.', 'danger')
            return redirect(url_for('main.editar_usuario', usuario_id=usuario.id))

        usuario.username = username
        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.cedula = cedula
        usuario.rango = rango
        usuario.rol = rol
        usuario.activo = activo
        if password:
            usuario.set_password(password)

        db.session.commit()
        flash(f'Datos de {usuario.nombre} {usuario.apellido} actualizados correctamente.', 'success')
        return redirect(url_for('main.gestionar_usuarios'))

    return render_template('admin/editar_usuario.html', usuario=usuario, rangos=RANGOS_BOMBERILES)


@main_bp.route('/admin/usuario/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
def eliminar_usuario(usuario_id):
    """
    Elimina un bombero del sistema. Exclusivo de administrador.
    No se permite borrar la propia cuenta ni a usuarios con reportes creados.
    """
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    usuario = Usuario.query.get_or_404(usuario_id)

    if usuario.id == current_user.id:
        flash('No puede eliminar su propia cuenta de administrador.', 'warning')
        return redirect(url_for('main.gestionar_usuarios'))

    if usuario.reportes_creados:
        flash(f'No se puede eliminar a {usuario.nombre} {usuario.apellido}: tiene '
              f'{len(usuario.reportes_creados)} reporte(s) en el sistema. '
              'Puede desactivar su cuenta en la edición en su lugar.', 'warning')
        return redirect(url_for('main.gestionar_usuarios'))

    nombre_completo = f'{usuario.nombre} {usuario.apellido}'
    db.session.delete(usuario)
    db.session.commit()
    flash(f'El bombero {nombre_completo} fue eliminado del sistema.', 'success')
    return redirect(url_for('main.gestionar_usuarios'))


@main_bp.route('/admin/reporte/<int:reporte_id>/eliminar', methods=['POST'])
@login_required
def eliminar_reporte(reporte_id):
    """
    Elimina un reporte físico de la base de datos. Exclusivo de administrador.
    """
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))
        
    reporte = Reporte.query.get_or_404(reporte_id)
    nro_control = reporte.nro_control
    
    db.session.delete(reporte)
    db.session.commit()
    
    flash(f'Reporte {nro_control} eliminado correctamente.', 'success')
    return redirect(url_for('main.dashboard_admin'))


@main_bp.route('/admin/reporte/<int:reporte_id>/validar', methods=['POST'])
@login_required
def validar_reporte(reporte_id):
    """
    Cambia el estado del reporte a 'Validado' o 'Rechazado'. Exclusivo de administrador.
    """
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))
        
    reporte = Reporte.query.get_or_404(reporte_id)
    accion = request.form.get('accion')
    
    if accion == 'validar':
        reporte.estado = 'Validado'
        flash(f'Reporte {reporte.nro_control} validado con éxito.', 'success')
    elif accion == 'rechazar':
        reporte.estado = 'Rechazado'
        flash(f'Reporte {reporte.nro_control} rechazado.', 'warning')
        
    db.session.commit()
    return redirect(url_for('main.dashboard_admin'))


@main_bp.route('/admin/vehiculos')
@login_required
def gestionar_vehiculos():
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))
    vehiculos = Vehiculo.query.order_by(Vehiculo.unidad.asc()).all()
    return render_template('admin/vehiculos.html', vehiculos=vehiculos)


@main_bp.route('/admin/vehiculo/<int:vehiculo_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_vehiculo(vehiculo_id):
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)

    if request.method == 'POST':
        vehiculo.unidad = request.form.get('unidad')
        vehiculo.placa = request.form.get('placa')
        vehiculo.marca = request.form.get('marca')
        vehiculo.modelo = request.form.get('modelo')
        vehiculo.color = request.form.get('color')
        vehiculo.tipo = request.form.get('tipo')

        db.session.commit()
        flash(f'Vehículo {vehiculo.unidad} actualizado correctamente.', 'success')
        return redirect(url_for('main.gestionar_vehiculos'))

    return render_template('admin/editar_vehiculo.html', vehiculo=vehiculo)


@main_bp.route('/admin/vehiculo/<int:vehiculo_id>/eliminar', methods=['POST'])
@login_required
def eliminar_vehiculo(vehiculo_id):
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    unidad = vehiculo.unidad

    db.session.delete(vehiculo)
    db.session.commit()

    flash(f'Vehículo {unidad} eliminado correctamente.', 'success')
    return redirect(url_for('main.gestionar_vehiculos'))


@main_bp.route('/admin/vehiculo/<int:vehiculo_id>/toggle', methods=['POST'])
@login_required
def toggle_vehiculo(vehiculo_id):
    if not current_user.es_admin:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    vehiculo.activo = not vehiculo.activo
    db.session.commit()

    estado = "activado" if vehiculo.activo else "desactivado"
    flash(f'Vehículo {vehiculo.unidad} {estado} correctamente.', 'success')
    return redirect(url_for('main.gestionar_vehiculos'))
