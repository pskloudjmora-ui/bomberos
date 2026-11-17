from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import RANGOS_BOMBERILES, Usuario, Vehiculo, db
from app.permisos import solo_administrador

auth_bp = Blueprint('auth', __name__)

ROLES_VALIDOS = ('bombero', 'administrador')


def _destino_seguro(destino):
    """Evita redirecciones abiertas: solo se permiten rutas internas."""
    if not destino:
        return None
    partes = urlparse(destino)
    if partes.scheme or partes.netloc:
        return None
    if not destino.startswith('/') or destino.startswith('//'):
        return None
    return destino


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        remember = bool(request.form.get('remember'))

        usuario = Usuario.query.filter_by(username=username).first()

        if not usuario or not usuario.check_password(password):
            flash('Usuario o contraseña incorrectos. Por favor intente de nuevo.', 'danger')
            return redirect(url_for('auth.login'))

        if not usuario.activo:
            flash('Esta cuenta se encuentra inactiva. Contacte al administrador.', 'warning')
            return redirect(url_for('auth.login'))

        login_user(usuario, remember=remember)
        next_page = _destino_seguro(request.args.get('next'))
        return redirect(next_page) if next_page else redirect(url_for('main.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/registrar', methods=['GET', 'POST'])
@login_required
@solo_administrador
def registrar_usuario():
    """
    Ruta para que un Administrador pueda registrar nuevos bomberos en el sistema.
    """
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        nombre = (request.form.get('nombre') or '').strip()
        apellido = (request.form.get('apellido') or '').strip()
        cedula = (request.form.get('cedula') or '').strip()
        rango = (request.form.get('rango') or '').strip()
        rol = request.form.get('rol', 'bombero')
        password = request.form.get('password') or ''

        # Validación mínima en servidor (no confiar solo en el navegador)
        faltantes = [campo for campo, valor in (
            ('nombre de usuario', username), ('nombre', nombre),
            ('apellido', apellido), ('cédula', cedula), ('contraseña', password),
        ) if not valor]
        if faltantes:
            flash('Complete los campos obligatorios: ' + ', '.join(faltantes) + '.', 'danger')
            return redirect(url_for('auth.registrar_usuario'))

        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return redirect(url_for('auth.registrar_usuario'))

        if rol not in ROLES_VALIDOS:
            rol = 'bombero'

        # Validación de unicidad
        usuario_existente = Usuario.query.filter(
            (Usuario.username == username) | (Usuario.cedula == cedula)
        ).first()
        if usuario_existente:
            flash('Error: El nombre de usuario o la cédula ya se encuentran registrados.', 'danger')
            return redirect(url_for('auth.registrar_usuario'))

        nuevo_usuario = Usuario(
            username=username,
            nombre=nombre,
            apellido=apellido,
            cedula=cedula,
            rango=rango,
            rol=rol
        )
        nuevo_usuario.set_password(password)

        db.session.add(nuevo_usuario)
        db.session.commit()

        flash(f'Bombero {nombre} {apellido} registrado exitosamente.', 'success')
        return redirect(url_for('main.gestionar_usuarios'))

    return render_template('auth/registrar.html', rangos=RANGOS_BOMBERILES)


@auth_bp.route('/registrar-vehiculo', methods=['GET', 'POST'])
@login_required
@solo_administrador
def registrar_vehiculo():
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
            return redirect(url_for('auth.registrar_vehiculo'))

        vehiculo_existente = Vehiculo.query.filter(
            (Vehiculo.unidad == unidad) | (Vehiculo.placa == placa)
        ).first()
        if vehiculo_existente:
            flash('Error: El número de unidad o la placa ya se encuentran registrados.', 'danger')
            return redirect(url_for('auth.registrar_vehiculo'))

        nuevo_vehiculo = Vehiculo(
            unidad=unidad,
            placa=placa,
            marca=marca,
            modelo=modelo,
            color=color,
            tipo=tipo
        )

        db.session.add(nuevo_vehiculo)
        db.session.commit()

        flash(f'Unidad {unidad} registrada exitosamente.', 'success')
        return redirect(url_for('main.gestionar_vehiculos'))

    return render_template('auth/registrar_vehiculo.html')
