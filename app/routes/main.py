from datetime import datetime, timedelta
from collections import Counter

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, or_
from sqlalchemy.exc import IntegrityError

from app.etiquetas import etiqueta_tipo
from app.models import (
    RANGOS_BOMBERILES,
    Reporte,
    ReporteServicioAgua,
    ReporteServicioBaldeo,
    ReporteVehiculoActuante,
    Usuario,
    Vehiculo,
    db,
)
from app.permisos import solo_administrador
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
    reportes = Reporte.query.filter_by(creador_id=current_user.id).order_by(
        Reporte.fecha.desc(), Reporte.hora_aviso.desc()
    ).all()
    return render_template('bombero/historial.html', reportes=reportes)


@main_bp.route('/admin/dashboard')
@login_required
@solo_administrador
def dashboard_admin():
    """
    Dashboard principal del Administrador.
    Muestra Métricas Clave (KPIs) y datos para los gráficos mediante consultas agregadas.
    Permite filtrar incidencias por rango de fechas, tipo de reporte y vehículo.
    """
    # 1. OBTENCIÓN DE FILTROS DE BÚSQUEDA
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    tipo_reporte_filtro = request.args.get('tipo_reporte')
    vehiculo_filtro = request.args.get('vehiculo')  # ID del vehículo

    hoy = datetime.now().date()
    try:
        fecha_inicio = (
            datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            if fecha_inicio_str else (hoy - timedelta(days=30))
        )
        fecha_fin = (
            datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            if fecha_fin_str else hoy
        )
    except ValueError:
        flash('El rango de fechas no es válido. Se muestran los últimos 30 días.', 'warning')
        fecha_inicio = hoy - timedelta(days=30)
        fecha_fin = hoy

    # Filtros comunes: se aplican por igual a KPIs, gráficos y tabla para que
    # todas las cifras del panel sean coherentes entre sí.
    filtros = [Reporte.fecha >= fecha_inicio, Reporte.fecha <= fecha_fin]

    if vehiculo_filtro and vehiculo_filtro != 'Todos':
        try:
            filtros.append(Reporte.vehiculos_actuantes.any(vehiculo_id=int(vehiculo_filtro)))
        except (TypeError, ValueError):
            flash('El vehículo seleccionado no es válido.', 'warning')

    # La columna `tipo_reporte` guarda la identidad polimórfica genérica
    # ('incendio', 'rescate_especializado', ...), así que el filtro por tipo
    # específico (p. ej. 'incendio_estructura' o 'rescate_caida') se aplica en
    # memoria usando la propiedad `tipo_especifico`.
    reportes_filtrados = Reporte.query.filter(*filtros).order_by(
        Reporte.fecha.desc(), Reporte.id.desc()
    ).all()

    if tipo_reporte_filtro and tipo_reporte_filtro != 'Todos':
        reportes_filtrados = [
            r for r in reportes_filtrados if r.tipo_especifico == tipo_reporte_filtro
        ]

    # 2. KPIs CALCULADOS SOBRE EL MISMO CONJUNTO FILTRADO
    # A. Total de incidencias en el período filtrado
    total_incidencias = len(reportes_filtrados)

    # B. Litros totales de agua distribuidos (Abastecimiento de Agua + Baldeo)
    litros_totales_agua = 0
    for reporte in reportes_filtrados:
        if isinstance(reporte, ReporteServicioAgua):
            litros_totales_agua += reporte.litros_distribuidos or 0
        elif isinstance(reporte, ReporteServicioBaldeo):
            litros_totales_agua += reporte.litros_agua_utilizados or 0

    # C. Tipo de servicio más frecuente y desglose para el gráfico
    conteo_tipos = Counter(r.tipo_especifico for r in reportes_filtrados)
    if conteo_tipos:
        tipo_mas_frecuente, tipo_mas_frecuente_cant = conteo_tipos.most_common(1)[0]
    else:
        tipo_mas_frecuente, tipo_mas_frecuente_cant = 'Ninguno', 0

    datos_grafico_pastel = {
        etiqueta_tipo(tipo): total for tipo, total in conteo_tipos.most_common()
    }

    # D. Cálculo de Tiempo Promedio de Respuesta (aviso -> llegada)
    tiempo_promedio_minutos = 0
    tiempos_validos = 0

    for reporte in reportes_filtrados:
        h_aviso, h_llegada = reporte.hora_aviso, reporte.hora_llegada
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
    # Desglose de incidencias por fecha (para gráfico de líneas - tendencia)
    conteo_fechas = Counter(r.fecha for r in reportes_filtrados)

    fechas_grafico = [fecha.strftime('%d/%m') for fecha in sorted(conteo_fechas)]
    cantidades_grafico = [conteo_fechas[fecha] for fecha in sorted(conteo_fechas)]

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
        filtro_inicio=fecha_inicio.strftime('%Y-%m-%d'),
        filtro_fin=fecha_fin.strftime('%Y-%m-%d'),
        filtro_tipo=tipo_reporte_filtro or 'Todos',
        filtro_vehiculo=vehiculo_filtro or 'Todos'
    )


@main_bp.route('/admin/usuarios')
@login_required
@solo_administrador
def gestionar_usuarios():
    """
    Visualiza la lista de usuarios y bomberos registrados con filtros de búsqueda
    (texto, rango, rol y estado). Exclusivo de administrador.
    """
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
@solo_administrador
def lista_bomberos_imprimir():
    """
    Vista imprimible (lista oficial) del personal bomberil filtrado por los
    mismos criterios de búsqueda de la gestión. Exclusivo de administrador.
    """
    query, filtros = _aplicar_filtros_usuarios(request.args)
    usuarios = query.order_by(
        _orden_jerarquia(Usuario.rango).asc(),
        Usuario.nombre.asc()
    ).all()

    fecha_emision = datetime.now().strftime('%d/%m/%Y %H:%M')

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
@solo_administrador
def ver_usuario(usuario_id):
    """
    Visualiza el detalle completo de un bombero: datos personales, credenciales
    de acceso y reportes que ha elaborado. Exclusivo de administrador.
    """
    usuario = Usuario.query.get_or_404(usuario_id)
    reportes = Reporte.query.filter_by(creador_id=usuario.id).order_by(Reporte.fecha.desc()).all()
    return render_template('admin/ver_usuario.html', usuario=usuario, reportes=reportes)


@main_bp.route('/admin/usuario/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
@solo_administrador
def editar_usuario(usuario_id):
    """
    Edita los datos y credenciales de un bombero. Exclusivo de administrador.
    Si se deja la contraseña en blanco, se conserva la actual.
    """
    usuario = Usuario.query.get_or_404(usuario_id)

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        nombre = (request.form.get('nombre') or '').strip()
        apellido = (request.form.get('apellido') or '').strip()
        cedula = (request.form.get('cedula') or '').strip()
        rango = (request.form.get('rango') or '').strip()
        rol = request.form.get('rol', 'bombero')
        activo = request.form.get('activo') == 'on'
        password = request.form.get('password') or ''

        faltantes = [campo for campo, valor in (
            ('nombre de usuario', username), ('nombre', nombre),
            ('apellido', apellido), ('cédula', cedula),
        ) if not valor]
        if faltantes:
            flash('Complete los campos obligatorios: ' + ', '.join(faltantes) + '.', 'danger')
            return redirect(url_for('main.editar_usuario', usuario_id=usuario.id))

        if rol not in ('bombero', 'administrador'):
            rol = 'bombero'

        if password and len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return redirect(url_for('main.editar_usuario', usuario_id=usuario.id))

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

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('No se pudo guardar: los datos entran en conflicto con otro usuario.', 'danger')
            return redirect(url_for('main.editar_usuario', usuario_id=usuario.id))

        flash(f'Datos de {usuario.nombre} {usuario.apellido} actualizados correctamente.', 'success')
        return redirect(url_for('main.gestionar_usuarios'))

    return render_template('admin/editar_usuario.html', usuario=usuario, rangos=RANGOS_BOMBERILES)


@main_bp.route('/admin/usuario/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
@solo_administrador
def eliminar_usuario(usuario_id):
    """
    Elimina un bombero del sistema. Exclusivo de administrador.
    No se permite borrar la propia cuenta ni a usuarios con reportes creados.
    """
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
    try:
        db.session.delete(usuario)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(f'No se puede eliminar a {nombre_completo}: tiene registros asociados. '
              'Desactive su cuenta en lugar de eliminarla.', 'warning')
        return redirect(url_for('main.gestionar_usuarios'))

    flash(f'El bombero {nombre_completo} fue eliminado del sistema.', 'success')
    return redirect(url_for('main.gestionar_usuarios'))


@main_bp.route('/admin/reporte/<int:reporte_id>/eliminar', methods=['POST'])
@login_required
@solo_administrador
def eliminar_reporte(reporte_id):
    """
    Elimina un reporte físico de la base de datos. Exclusivo de administrador.
    """
    reporte = Reporte.query.get_or_404(reporte_id)
    nro_control = reporte.nro_control

    try:
        db.session.delete(reporte)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(f'No se pudo eliminar el reporte {nro_control}: tiene registros asociados.', 'danger')
        return redirect(url_for('main.dashboard_admin'))

    flash(f'Reporte {nro_control} eliminado correctamente.', 'success')
    return redirect(url_for('main.dashboard_admin'))


@main_bp.route('/admin/reporte/<int:reporte_id>/validar', methods=['POST'])
@login_required
@solo_administrador
def validar_reporte(reporte_id):
    """
    Cambia el estado del reporte a 'Validado' o 'Rechazado'. Exclusivo de administrador.
    """
    reporte = Reporte.query.get_or_404(reporte_id)
    accion = request.form.get('accion')

    if accion == 'validar':
        reporte.estado = 'Validado'
        flash(f'Reporte {reporte.nro_control} validado con éxito.', 'success')
    elif accion == 'rechazar':
        reporte.estado = 'Rechazado'
        flash(f'Reporte {reporte.nro_control} rechazado.', 'warning')
    else:
        flash('Acción no reconocida.', 'warning')
        return redirect(url_for('main.dashboard_admin'))

    db.session.commit()
    return redirect(url_for('main.dashboard_admin'))


@main_bp.route('/admin/vehiculos')
@login_required
@solo_administrador
def gestionar_vehiculos():
    vehiculos = Vehiculo.query.order_by(Vehiculo.unidad.asc()).all()
    return render_template('admin/vehiculos.html', vehiculos=vehiculos)


@main_bp.route('/admin/vehiculo/<int:vehiculo_id>/editar', methods=['GET', 'POST'])
@login_required
@solo_administrador
def editar_vehiculo(vehiculo_id):
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)

    if request.method == 'POST':
        unidad = (request.form.get('unidad') or '').strip()
        placa = (request.form.get('placa') or '').strip()
        marca = (request.form.get('marca') or '').strip()
        modelo = (request.form.get('modelo') or '').strip()
        color = (request.form.get('color') or '').strip()
        tipo = (request.form.get('tipo') or '').strip()

        faltantes = [campo for campo, valor in (
            ('unidad', unidad), ('placa', placa), ('marca', marca),
            ('modelo', modelo), ('tipo', tipo),
        ) if not valor]
        if faltantes:
            flash('Complete los campos obligatorios: ' + ', '.join(faltantes) + '.', 'danger')
            return redirect(url_for('main.editar_vehiculo', vehiculo_id=vehiculo.id))

        duplicado = Vehiculo.query.filter(
            ((Vehiculo.unidad == unidad) | (Vehiculo.placa == placa)) &
            (Vehiculo.id != vehiculo.id)
        ).first()
        if duplicado:
            flash('Error: La unidad o la placa ya pertenecen a otro vehículo.', 'danger')
            return redirect(url_for('main.editar_vehiculo', vehiculo_id=vehiculo.id))

        vehiculo.unidad = unidad
        vehiculo.placa = placa
        vehiculo.marca = marca
        vehiculo.modelo = modelo
        vehiculo.color = color
        vehiculo.tipo = tipo

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('No se pudo guardar: la unidad o la placa ya existen.', 'danger')
            return redirect(url_for('main.editar_vehiculo', vehiculo_id=vehiculo.id))

        flash(f'Vehículo {vehiculo.unidad} actualizado correctamente.', 'success')
        return redirect(url_for('main.gestionar_vehiculos'))

    return render_template('admin/editar_vehiculo.html', vehiculo=vehiculo)


@main_bp.route('/admin/vehiculo/<int:vehiculo_id>/eliminar', methods=['POST'])
@login_required
@solo_administrador
def eliminar_vehiculo(vehiculo_id):
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    unidad = vehiculo.unidad

    actuaciones = ReporteVehiculoActuante.query.filter_by(vehiculo_id=vehiculo.id).count()
    if actuaciones:
        flash(f'No se puede eliminar la unidad {unidad}: participa en {actuaciones} '
              'reporte(s). Desactívela en su lugar.', 'warning')
        return redirect(url_for('main.gestionar_vehiculos'))

    try:
        db.session.delete(vehiculo)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(f'No se puede eliminar la unidad {unidad}: tiene registros asociados. '
              'Desactívela en su lugar.', 'warning')
        return redirect(url_for('main.gestionar_vehiculos'))

    flash(f'Vehículo {unidad} eliminado correctamente.', 'success')
    return redirect(url_for('main.gestionar_vehiculos'))


@main_bp.route('/admin/vehiculo/<int:vehiculo_id>/toggle', methods=['POST'])
@login_required
@solo_administrador
def toggle_vehiculo(vehiculo_id):
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    vehiculo.activo = not vehiculo.activo
    db.session.commit()

    estado = "activado" if vehiculo.activo else "desactivado"
    flash(f'Vehículo {vehiculo.unidad} {estado} correctamente.', 'success')
    return redirect(url_for('main.gestionar_vehiculos'))
