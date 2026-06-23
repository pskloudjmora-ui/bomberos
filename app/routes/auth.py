from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, Usuario

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        usuario = Usuario.query.filter_by(username=username).first()
        
        if not usuario or not usuario.check_password(password):
            flash('Usuario o contraseña incorrectos. Por favor intente de nuevo.', 'danger')
            return redirect(url_for('auth.login'))
            
        if not usuario.activo:
            flash('Esta cuenta se encuentra inactiva. Contacte al administrador.', 'warning')
            return redirect(url_for('auth.login'))
            
        login_user(usuario, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('main.index'))
        
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_usuario():
    """
    Ruta para que un Administrador pueda registrar nuevos bomberos en el sistema.
    """
    # Control de Acceso: Solo administradores pueden registrar
    if not current_user.es_admin:
        flash('Acceso denegado: Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        cedula = request.form.get('cedula')
        rango = request.form.get('rango')
        rol = request.form.get('rol', 'bombero')
        password = request.form.get('password')
        
        # Validación
        usuario_existente = Usuario.query.filter((Usuario.username == username) | (Usuario.cedula == cedula)).first()
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
        
    return render_template('auth/registrar.html')
