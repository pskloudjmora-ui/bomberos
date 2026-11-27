# -*- coding: utf-8 -*-
"""
Módulo de Soporte: limpieza de datos, respaldos de la base de datos
y consulta del registro de actividades del sistema.
Accesible exclusivamente para el rol 'soporte'.
"""
import os
import shutil
import subprocess
from datetime import datetime
from functools import wraps

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user, login_required
from sqlalchemy import inspect as sa_inspect
from app import db
from app.models import LogActividad, Reporte, Respaldo, SecuenciaControl
from app.services.actividad import registrar_log

soporte_bp = Blueprint('soporte', __name__, url_prefix='/soporte')

def requiere_admin_o_soporte(vista):
    """Restringe la vista exclusivamente al rol 'soporte'."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        if current_user.rol != 'soporte':
            flash('Acceso denegado: esta sección es exclusiva del rol Soporte.', 'danger')
            return redirect(url_for('main.index'))
        return vista(*args, **kwargs)
    return envoltura


# ============================ PANEL ============================

@soporte_bp.route('/')
@login_required
@requiere_admin_o_soporte
def panel():
    total_logs = LogActividad.query.count()
    total_respaldos = Respaldo.query.count()
    ultimo_respaldo = Respaldo.query.order_by(Respaldo.fecha.desc()).first()
    total_reportes = Reporte.query.count()
    return render_template(
        'soporte/panel.html',
        total_logs=total_logs,
        total_respaldos=total_respaldos,
        ultimo_respaldo=ultimo_respaldo,
        total_reportes=total_reportes,
    )


# ============================ LIMPIAR DATA ============================

def _query_limpieza(form):
    """Construye el queryset de reportes según los filtros del formulario."""
    q = Reporte.query
    fi = (form.get('fecha_inicio') or '').strip()
    ff = (form.get('fecha_fin') or '').strip()
    if fi:
        q = q.filter(Reporte.fecha >= datetime.strptime(fi, '%Y-%m-%d').date())
    if ff:
        q = q.filter(Reporte.fecha <= datetime.strptime(ff, '%Y-%m-%d').date())
    estado = (form.get('estado') or '').strip()
    if estado and estado != 'Todos':
        q = q.filter(Reporte.estado == estado)
    return q


@soporte_bp.route('/limpiar', methods=['GET', 'POST'])
@login_required
@requiere_admin_o_soporte
def limpiar():
    if request.method == 'POST':
        if request.form.get('confirmar') != 'SI':
            flash('Debe confirmar la eliminación para continuar.', 'warning')
            return redirect(url_for('soporte.limpiar'))
        q = _query_limpieza(request.form)
        ids = [r.id for r in q.all()]
        eliminados = 0
        for rid in ids:
            rep = Reporte.query.get(rid)
            if rep:
                db.session.delete(rep)
                eliminados += 1
        db.session.commit()
        registrar_log('limpiar_data', f'{eliminados} reporte(s) eliminados')
        db.session.commit()
        flash(f'Se eliminaron {eliminados} reporte(s) del sistema.', 'success')
        return redirect(url_for('soporte.limpiar'))

    reportes = _query_limpieza(request.args).order_by(Reporte.fecha.desc()).limit(100).all()
    return render_template('soporte/limpiar.html', reportes=reportes)


# ============================ RESPALDOS ============================

def _ruta_respaldo(nombre):
    carpeta = os.path.join(current_app.instance_path, 'respaldos')
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, nombre)


def _dump_json_tablas():
    """Exporta todas las tablas a un JSON (fallback universal)."""
    datos = {}
    for tabla in db.metadata.sorted_tables:
        rows = db.session.execute(tabla.select()).fetchall()
        datos[tabla.name] = [dict(r._mapping) for r in rows]
    return datos


def _sql_literal(valor):
    """Convierte un valor de Python al literal SQL correspondiente."""
    import datetime as _dt
    import decimal
    if valor is None:
        return 'NULL'
    if isinstance(valor, bool):
        return 'TRUE' if valor else 'FALSE'
    if isinstance(valor, (int, float, decimal.Decimal)):
        return str(valor)
    if isinstance(valor, (_dt.datetime, _dt.date, _dt.time)):
        return "'" + valor.isoformat() + "'"
    if isinstance(valor, (bytes, bytearray, memoryview)):
        return "'\\x" + bytes(valor).hex() + "'"
    return "'" + str(valor).replace("'", "''") + "'"


def _dump_sql_tablas():
    """Genera un script SQL con INSERTs de todas las tablas (portable)."""
    lineas = [
        '-- Respaldo generado por el Sistema de Reportes BOMBEROS',
        f'-- Fecha: {datetime.now().isoformat(timespec="seconds")}',
        '',
    ]
    for tabla in db.metadata.sorted_tables:
        cols = [c.name for c in tabla.columns]
        col_sql = ', '.join(f'"{c}"' for c in cols)
        lineas.append(f'-- Tabla: {tabla.name}')
        rows = db.session.execute(tabla.select()).fetchall()
        if not rows:
            lineas.append(f'-- (sin registros) {tabla.name}')
            lineas.append('')
            continue
        for r in rows:
            vals = ', '.join(_sql_literal(v) for v in r._mapping.values())
            lineas.append(f'INSERT INTO "{tabla.name}" ({col_sql}) VALUES ({vals});')
        lineas.append('')
    return '\n'.join(lineas)


def _generar_archivo_respaldo():
    """
    Genera el archivo de respaldo según el motor de BD:
    - SQLite: copia directa del archivo .db
    - PostgreSQL: intenta pg_dump; si no está disponible, dump JSON de tablas
    Devuelve (ruta_absoluta, tipo, nombre_archivo).
    """
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')

    if uri.startswith('sqlite'):
        ruta_db = uri.replace('sqlite:///', '', 1)
        if not os.path.isabs(ruta_db):
            ruta_db = os.path.join(current_app.root_path, '..', ruta_db)
        nombre = f'respaldo_{stamp}.db'
        destino = _ruta_respaldo(nombre)
        shutil.copy2(os.path.abspath(ruta_db), destino)
        return destino, 'sqlite', nombre

    # PostgreSQL (Render)
    nombre_sql = f'respaldo_{stamp}.sql'
    destino_sql = _ruta_respaldo(nombre_sql)
    try:
        resultado = subprocess.run(
            ['pg_dump', uri, '-f', destino_sql],
            capture_output=True, text=True, timeout=120,
        )
        if resultado.returncode == 0 and os.path.exists(destino_sql):
            return destino_sql, 'postgres', nombre_sql
    except Exception:
        pass

    # Fallback portable: script SQL con INSERTs de todas las tablas
    nombre = f'respaldo_{stamp}.sql'
    destino = _ruta_respaldo(nombre)
    with open(destino, 'w', encoding='utf-8') as f:
        f.write(_dump_sql_tablas())
    return destino, 'sql', nombre


@soporte_bp.route('/respaldos', methods=['GET', 'POST'])
@login_required
@requiere_admin_o_soporte
def respaldos():
    if request.method == 'POST':
        try:
            ruta, tipo, nombre = _generar_archivo_respaldo()
        except Exception as exc:
            flash(f'No se pudo generar el respaldo: {exc}', 'danger')
            return redirect(url_for('soporte.respaldos'))
        tamano = os.path.getsize(ruta)
        db.session.add(Respaldo(
            nombre_archivo=nombre, tipo=tipo, tamano_bytes=tamano,
            usuario_id=current_user.id,
        ))
        db.session.commit()
        registrar_log('respaldo_creado', f'{nombre} ({tipo}, {tamano} bytes)')
        db.session.commit()
        flash(f'Respaldo generado: {nombre}', 'success')
        return redirect(url_for('soporte.respaldos'))

    lista = Respaldo.query.order_by(Respaldo.fecha.desc()).all()
    return render_template('soporte/respaldos.html', respaldos=lista)


@soporte_bp.route('/respaldos/<int:respaldo_id>/descargar')
@login_required
@requiere_admin_o_soporte
def descargar_respaldo(respaldo_id):
    res = Respaldo.query.get_or_404(respaldo_id)
    ruta = _ruta_respaldo(res.nombre_archivo)
    if not os.path.exists(ruta):
        flash('El archivo de respaldo ya no existe en el servidor.', 'danger')
        return redirect(url_for('soporte.respaldos'))
    registrar_log('respaldo_descargado', res.nombre_archivo)
    db.session.commit()
    return send_file(ruta, as_attachment=True, download_name=res.nombre_archivo)


# ============================ CONEXIÓN A BD ============================

def _info_conexion_bd():
    """Diagnóstico de la conexión a la base de datos."""
    from sqlalchemy import text
    import time

    engine = db.engine
    info = {
        'dialecto': engine.dialect.name,
        'driver': engine.dialect.driver,
        'uri_mostrada': '(oculta)',
        'estado': 'Desconocido',
        'error': None,
        'latencia_ms': None,
        'conexiones_activas': None,
        'tablas': 0,
        'detalle_extra': '',
    }

    # Mostrar URI sin credenciales
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if uri.startswith('sqlite'):
        info['uri_mostrada'] = uri
        info['detalle_extra'] = uri.replace('sqlite:///', '')
    elif '://' in uri:
        desde = uri.find('://') + 3
        info['uri_mostrada'] = uri[:desde] + '***@' + uri[uri.rfind('@') + 1:] if '@' in uri else uri

    # Probar conexión con latencia
    try:
        inicio = time.time()
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
            info['latencia_ms'] = round((time.time() - inicio) * 1000, 1)
            info['estado'] = 'Activa'

            if engine.dialect.name == 'postgresql':
                # Conexiones activas en el servidor Postgres
                try:
                    rows = conn.execute(text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                    )).scalar()
                    info['conexiones_activas'] = rows
                except Exception:
                    info['conexiones_activas'] = 'No disponible'
            elif engine.dialect.name == 'sqlite':
                info['conexiones_activas'] = 'N/A (archivo local)'
                ruta = uri.replace('sqlite:///', '', 1)
                if os.path.exists(ruta):
                    info['detalle_extra'] = f'{os.path.abspath(ruta)} ({os.path.getsize(ruta) / 1024:.1f} KB)'
        info['tablas'] = len(sa_inspect(engine).get_table_names())
    except Exception as exc:
        info['estado'] = 'Error'
        info['error'] = str(exc)

    return info


def _info_postgres_externo():
    """
    Prueba la conexión a PostgreSQL usando las variables de entorno
    DATABASE_URL / RENDER_DATABASE_URL, aunque la app activa sea SQLite.
    """
    import time
    from sqlalchemy import create_engine, text

    url = os.environ.get('DATABASE_URL') or os.environ.get('RENDER_DATABASE_URL')
    if not url:
        return {'configurada': False}
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    # SSL solo para hosts remotos; localhost normalmente no soporta SSL
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or '').lower()
    if 'sslmode' not in url and host not in ('localhost', '127.0.0.1', '::1'):
        url += ('&' if '?' in url else '?') + 'sslmode=require'

    info = {'configurada': True, 'uri_mostrada': url[:url.find('://') + 3] + '***@' + url[url.rfind('@') + 1:] if '@' in url else url}
    try:
        motor = create_engine(url)
        inicio = time.time()
        with motor.connect() as conn:
            conn.execute(text('SELECT 1'))
            info['estado'] = 'Activa'
            info['latencia_ms'] = round((time.time() - inicio) * 1000, 1)
            try:
                info['conexiones_activas'] = conn.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                )).scalar()
            except Exception:
                info['conexiones_activas'] = 'No disponible'
            try:
                info['version'] = conn.execute(text('SHOW server_version')).scalar()
            except Exception:
                info['version'] = None
        motor.dispose()
    except Exception as exc:
        info['estado'] = 'Error'
        info['error'] = str(exc)
    return info


def _test_postgres(url):
    """Prueba una URL de conexión PostgreSQL y devuelve info de diagnóstico."""
    import time
    from sqlalchemy import create_engine, text

    info = {'estado': None, 'error': None, 'latencia_ms': None,
            'conexiones_activas': None, 'version': None}
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    try:
        motor = create_engine(url)
        inicio = time.time()
        with motor.connect() as conn:
            conn.execute(text('SELECT 1'))
            info['estado'] = 'Activa'
            info['latencia_ms'] = round((time.time() - inicio) * 1000, 1)
            try:
                info['conexiones_activas'] = conn.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                )).scalar()
            except Exception:
                info['conexiones_activas'] = 'No disponible'
            try:
                info['version'] = conn.execute(text('SHOW server_version')).scalar()
            except Exception:
                info['version'] = None
        motor.dispose()
    except Exception as exc:
        info['estado'] = 'Error'
        info['error'] = str(exc)
    return info


def _ruta_env():
    return os.path.join(current_app.root_path, '..', '.env')


def _leer_env():
    ruta = _ruta_env()
    if not os.path.exists(ruta):
        return []
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read().splitlines()


def _escribir_env(lineas):
    with open(_ruta_env(), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lineas) + '\n')


def _guardar_env_database_url(url):
    """Escribe/actualiza DATABASE_URL en el archivo .env del proyecto."""
    from urllib.parse import quote
    lineas = _leer_env()
    nueva = f'DATABASE_URL={url}'
    reemplazada = False
    for i, linea in enumerate(lineas):
        if linea.strip().startswith('DATABASE_URL='):
            lineas[i] = nueva
            reemplazada = True
    if not reemplazada:
        lineas.append(nueva)
    _escribir_env(lineas)


def _alternar_database_url(comentar):
    """
    Comenta (comentar=True) o descomenta (False) la línea DATABASE_URL
    del archivo .env para cambiar el motor de BD al reiniciar.
    Devuelve (exito, mensaje).
    """
    lineas = _leer_env()
    idx = next((i for i, l in enumerate(lineas)
                if l.strip().startswith('DATABASE_URL=')
                or l.strip().startswith('#DATABASE_URL=')), None)
    if comentar:
        if idx is None or lineas[idx].lstrip().startswith('#'):
            return False, 'No hay DATABASE_URL activa en .env para desactivar.'
        linea = lineas[idx].strip()
        lineas[idx] = '#' + linea
        _escribir_env(lineas)
        return True, 'Conexión cambiada a SQLite en .env. Reinicie el servidor para aplicar.'
    if idx is None:
        return False, 'No hay DATABASE_URL guardada en .env. Configure PostgreSQL abajo primero.'
    linea = lineas[idx].strip()
    if linea.startswith('#'):
        lineas[idx] = linea.lstrip('#').strip()
        _escribir_env(lineas)
        return True, 'Conexión cambiada a PostgreSQL en .env. Reinicie el servidor para aplicar.'
    return True, 'DATABASE_URL ya está activa en .env.'


def _ruta_sqlite_local():
    """Localiza el archivo SQLite local del proyecto."""
    candidatos = [
        os.path.join(current_app.root_path, '..', 'bomberos.db'),
        os.path.join(current_app.instance_path, 'bomberos.db'),
    ]
    for ruta in candidatos:
        if os.path.exists(ruta):
            return os.path.abspath(ruta)
    return None


def _sincronizar_sqlite_a_postgres():
    """
    Copia todos los datos del SQLite local hacia la base PostgreSQL activa.
    Solo vuelca tablas destino vacías (no mezcla ni duplica registros).
    Devuelve (filas_insertadas, tablas_omitidas).
    """
    from sqlalchemy import create_engine, func, select

    if db.engine.dialect.name != 'postgresql':
        raise ValueError('La sincronización requiere que la app esté conectada a PostgreSQL.')
    ruta_sqlite = _ruta_sqlite_local()
    if not ruta_sqlite:
        raise ValueError('No se encontró el archivo bomberos.db (SQLite) del proyecto.')

    origen = create_engine(f'sqlite:///{ruta_sqlite}')
    insertados = 0
    omitidas = []
    try:
        with origen.connect() as sconn:
            tablas_origen = set(sa_inspect(origen).get_table_names())
            for tabla in db.metadata.sorted_tables:
                if tabla.name not in tablas_origen:
                    continue
                rows = [dict(r) for r in sconn.execute(tabla.select()).mappings()]
                if not rows:
                    continue
                existentes = db.session.execute(
                    select(func.count()).select_from(tabla)
                ).scalar()
                if existentes:
                    omitidas.append(f'{tabla.name} ({existentes} registros ya existentes)')
                    continue
                for i in range(0, len(rows), 500):
                    db.session.execute(tabla.insert(), rows[i:i + 500])
                insertados += len(rows)
        db.session.commit()

        # Resincronizar secuencias autoincrementales de Postgres
        from sqlalchemy import text
        for tabla in db.metadata.sorted_tables:
            if tabla.c.get('id') is None:
                continue
            try:
                db.session.execute(text(
                    "SELECT setval(pg_get_serial_sequence(:tabla, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM \"" + tabla.name + "\"), 0))"
                ), {'tabla': tabla.name})
            except Exception:
                db.session.rollback()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        origen.dispose()
    return insertados, omitidas


def _info_correlativo():
    """Estado actual del correlativo anual de reportes (solo lectura)."""
    anio = datetime.now().year
    seq = db.session.get(SecuenciaControl, anio)
    ultimo = seq.ultimo if seq else 0
    return {'anio': anio, 'ultimo': ultimo, 'proximo': ultimo + 1}


@soporte_bp.route('/conexion', methods=['GET', 'POST'])
@login_required
@requiere_admin_o_soporte
def conexion():
    info = _info_conexion_bd()
    pg_externo = _info_postgres_externo() if info['dialecto'] != 'postgresql' else None

    pg_form = {
        'host': request.values.get('pg_host', ''),
        'port': request.values.get('pg_port', '5432'),
        'database': request.values.get('pg_database', ''),
        'user': request.values.get('pg_user', ''),
        'password': request.values.get('pg_password', ''),
    }
    pg_test = None

    if request.method == 'POST':
        accion = request.form.get('accion')

        if accion == 'cambiar_motor':
            # Si está en Postgres -> comentar DATABASE_URL (SQLite); y viceversa
            ok, mensaje = _alternar_database_url(comentar=(info['dialecto'] == 'postgresql'))
            if ok:
                registrar_log('cambiar_motor_bd', mensaje)
                db.session.commit()
            flash(mensaje, 'success' if ok else 'danger')
            return redirect(url_for('soporte.conexion'))

        if accion == 'sincronizar':
            try:
                filas, omitidas = _sincronizar_sqlite_a_postgres()
            except Exception as exc:
                flash(f'No se pudo sincronizar: {exc}', 'danger')
            else:
                detalle = f'{filas} filas copiadas'
                if omitidas:
                    detalle += f'; omitidas: {", ".join(omitidas[:8])}'
                registrar_log('sincronizar_sqlite', detalle)
                db.session.commit()
                flash(f'Sincronización completada: {detalle}.', 'success')
            return redirect(url_for('soporte.conexion'))

        if accion == 'correlativo':
            try:
                valor = int((request.form.get('correlativo_inicio') or '0').strip())
            except ValueError:
                valor = 0
            if valor < 1:
                flash('El correlativo de inicio debe ser un número mayor o igual a 1.', 'danger')
            else:
                anio = datetime.now().year
                seq = db.session.get(SecuenciaControl, anio)
                if seq is None:
                    seq = SecuenciaControl(anio=anio, ultimo=0)
                    db.session.add(seq)
                seq.ultimo = valor - 1
                db.session.commit()
                registrar_log('configurar_correlativo', f'Inicio {valor:07d}-{anio}')
                db.session.commit()
                flash(f'Correlativo configurado: el próximo reporte será {valor:07d}-{anio}.', 'success')
            return redirect(url_for('soporte.conexion'))

        # Construir URL desde los campos (sin credenciales en logs)
        from urllib.parse import quote
        host = pg_form['host'].strip()
        if host:
            user = quote(pg_form['user'].strip(), safe='')
            pwd = quote(pg_form['password'], safe='')
            dbname = pg_form['database'].strip()
            port = pg_form['port'].strip() or '5432'
            url = f'postgresql://{user}:{pwd}@{host}:{port}/{dbname}'
            pg_form['url'] = url

            if accion == 'probar':
                pg_test = _test_postgres(url)
                pg_test['uri_mostrada'] = url[:url.find('://') + 3] + '***@' + url[url.rfind('@') + 1:]
            elif accion == 'guardar':
                if pg_test is None:
                    pg_test = _test_postgres(url)
                if pg_test['estado'] == 'Activa':
                    _guardar_env_database_url(url)
                    registrar_log('configurar_postgres', f'Guardada conexión a {host}:{port}/{dbname}')
                    db.session.commit()
                    flash('Conexión PostgreSQL guardada en .env. Reinicie el servidor para aplicarla.', 'success')
                else:
                    flash('No se guardó: la conexión de prueba falló. Corrija los datos e intente de nuevo.', 'danger')
                return redirect(url_for('soporte.conexion'))

    return render_template(
        'soporte/conexion.html',
        info=info, pg_externo=pg_externo,
        pg_form=pg_form, pg_test=pg_test,
        correlativo=_info_correlativo(),
    )


# ============================ LOGS ============================

@soporte_bp.route('/logs')
@login_required
@requiere_admin_o_soporte
def logs():
    q = LogActividad.query
    usuario_f = (request.args.get('usuario') or '').strip()
    accion_f = (request.args.get('accion') or '').strip()
    if usuario_f:
        q = q.filter(LogActividad.username.ilike(f'%{usuario_f}%'))
    if accion_f:
        q = q.filter(LogActividad.accion.ilike(f'%{accion_f}%'))
    registros = q.order_by(LogActividad.fecha.desc()).limit(500).all()
    acciones = db.session.query(LogActividad.accion).distinct().all()
    return render_template(
        'soporte/logs.html',
        logs=registros,
        filtro_usuario=usuario_f,
        filtro_accion=accion_f,
        acciones_disponibles=sorted(a[0] for a in acciones),
    )
