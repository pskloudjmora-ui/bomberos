from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config
from app.models import db, Usuario

migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Usuario, int(user_id))
    except (TypeError, ValueError):
        return None


# Columnas agregadas después de la creación inicial de las tablas.
# `db.create_all()` no altera tablas existentes, por lo que estos ajustes se
# aplican de forma idempotente al arrancar (compatible con SQLite y PostgreSQL).
COLUMNAS_NUEVAS = {
    'reportes': {
        'itinerario_ruta': 'TEXT',
        'cuadrante_paz': 'VARCHAR(100)',
    },
    'reporte_vehiculos_actuantes': {
        'hora_salida': 'TIME',
    },
    'reportes_incendio': {
        'tipo_estructura': 'VARCHAR(100)',
        'tipo_apoyo': 'VARCHAR(50)',
        'salida_primera_maquina': 'TIME',
        'salida_segunda_maquina': 'TIME',
        'salida_ambulancia': 'TIME',
        'salida_unidad_adicional': 'TIME',
        'salida_unidad_adicional_nombre': 'VARCHAR(100)',
        'inmueble_descripcion': 'VARCHAR(50)',
        'inmueble_valor': 'NUMERIC(14, 2)',
        'inmueble_perdidas': 'NUMERIC(14, 2)',
        'inmueble_aseguradora': 'VARCHAR(150)',
        'mueble_propietario': 'VARCHAR(150)',
        'mueble_propietario_ci': 'VARCHAR(30)',
        'mueble_valor': 'NUMERIC(14, 2)',
        'mueble_perdidas': 'NUMERIC(14, 2)',
        'mueble_aseguradora': 'VARCHAR(150)',
        'mueble_condicion': 'VARCHAR(100)',
        'lugar_a_cargo': 'VARCHAR(150)',
        'sistema_electrico_tipo': 'VARCHAR(100)',
        'sistema_electrico_capacidad': 'VARCHAR(100)',
        'sistema_electrico_uso': 'VARCHAR(150)',
        'sistema_electrico_serial': 'VARCHAR(100)',
        'sistema_electrico_propiedad': 'VARCHAR(150)',
        'sistema_electrico_rif': 'VARCHAR(30)',
        'desperdicio_materia': 'VARCHAR(150)',
        'desperdicio_cantidad': 'VARCHAR(100)',
        'desperdicio_recuperable': 'VARCHAR(5)',
        'arbol_edad': 'VARCHAR(50)',
        'arbol_longitud': 'VARCHAR(50)',
        'arbol_circunferencia': 'VARCHAR(50)',
        'arbol_especie': 'VARCHAR(150)',
        'vehiculos_afectados_json': 'TEXT',
    },
    'reportes_falsa_alarma': {
        'descripcion': 'TEXT',
    },
    'reportes_matpel_glp': {
        'serial_cilindro': 'VARCHAR(50)',
    },
    'reportes_matpel_otros': {
        'serial_cilindro': 'VARCHAR(50)',
        'clasificacion_servicio': 'VARCHAR(100)',
        'nombre_producto': 'VARCHAR(150)',
        'un_numero': 'VARCHAR(10)',
        'riesgo_producto': 'VARCHAR(150)',
        'tipo_almacenamiento': 'VARCHAR(100)',
        'certificado_bomberil': 'BOOLEAN',
        'nro_certificado': 'VARCHAR(50)',
        'propietario_nombre': 'VARCHAR(150)',
        'propietario_rif_ci': 'VARCHAR(30)',
        'empresa_distribuidora': 'VARCHAR(150)',
        'vehiculo_marca': 'VARCHAR(50)',
        'vehiculo_modelo': 'VARCHAR(50)',
        'vehiculo_placa': 'VARCHAR(20)',
        'vehiculo_color': 'VARCHAR(30)',
        'vehiculo_afecto': 'BOOLEAN',
        'hoja_seguridad': 'BOOLEAN',
        'extintor': 'BOOLEAN',
        'equipo_derrame': 'BOOLEAN',
    },
    'reportes_rescate_especializado': {
        'tipo_terreno': 'VARCHAR(100)',
        'cadaver_nombre': 'VARCHAR(150)',
        'cadaver_cedula': 'VARCHAR(20)',
        'cadaver_edad': 'INTEGER',
        'cadaver_sexo': 'VARCHAR(20)',
        'cadaver_ubicacion': 'VARCHAR(255)',
    },
    'reportes_aph_traslado': {
        'causa_traslado': 'TEXT',
        'recomendaciones': 'TEXT',
    },
    'reportes_aph_no_traslado': {
        'causa_traslado': 'TEXT',
        'recomendaciones': 'TEXT',
    },
    'reportes_aph_interhospitalario': {
        'causa_traslado': 'TEXT',
        'recomendaciones': 'TEXT',
    },
    'reportes_aph_sin_traslado': {
        'causa_traslado': 'TEXT',
        'recomendaciones': 'TEXT',
    },
}


def _asegurar_columnas_nuevas(app):
    """Agrega columnas faltantes a tablas ya existentes (migración mínima)."""
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(db.engine)
        tablas = set(inspector.get_table_names())
        for tabla, columnas in COLUMNAS_NUEVAS.items():
            if tabla not in tablas:
                continue
            existentes = {c['name'] for c in inspector.get_columns(tabla)}
            for nombre, tipo in columnas.items():
                if nombre in existentes:
                    continue
                db.session.execute(text(f'ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}'))
                db.session.commit()
                app.logger.warning('Esquema actualizado: %s.%s agregada.', tabla, nombre)
    except Exception as error:  # noqa: BLE001 - no debe impedir el arranque
        db.session.rollback()
        app.logger.error('No se pudo verificar el esquema: %s', error)


def crear_usuarios_defecto(app):
    """Crea usuarios semilla para pruebas iniciales si la BD está vacía.

    Solo se ejecuta en desarrollo (ver Config.SEED_DEMO_USERS): en producción
    las cuentas se crean desde la gestión de usuarios con contraseñas propias.
    """
    if not app.config.get('SEED_DEMO_USERS', False):
        return

    # Verificar si ya existen usuarios (no re-crear si hay datos reales)
    if Usuario.query.first() is not None:
        return

    # Crear Admin
    admin = Usuario(
        username='admin',
        nombre='Jefe',
        apellido='Administrador',
        cedula='V-12345678',
        rango='Coronel',
        rol='administrador'
    )
    admin.set_password('admin123')
    db.session.add(admin)

    # Crear Bombero de prueba
    bombero = Usuario(
        username='bombero',
        nombre='Juan',
        apellido='Pérez',
        cedula='V-87654321',
        rango='Cabo Primero',
        rol='bombero'
    )
    bombero.set_password('bombero123')
    db.session.add(bombero)

    db.session.commit()
    app.logger.warning('Usuarios de prueba creados: admin/admin123 y bombero/bombero123')


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializar base de datos y extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Registrar Blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.reportes import reportes_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(reportes_bp, url_prefix='/reportes')

    # Filtros de plantilla para mostrar los tipos de reporte de forma uniforme
    from app.etiquetas import ETIQUETAS_TIPO, color_tipo, etiqueta_tipo

    app.jinja_env.filters['etiqueta_tipo'] = etiqueta_tipo
    app.jinja_env.filters['color_tipo'] = color_tipo
    app.jinja_env.globals['tipos_reporte'] = ETIQUETAS_TIPO

    @app.before_request
    def bloquear_usuarios_inactivos():
        """Cierra la sesión si la cuenta fue desactivada durante la sesión."""
        if current_user.is_authenticated and not current_user.activo:
            logout_user()
            flash('Su cuenta fue desactivada. Contacte al administrador.', 'warning')
            return redirect(url_for('auth.login'))

    @app.errorhandler(CSRFError)
    def manejar_csrf(error):
        app.logger.warning('CSRF rechazado en %s: %s', request.path, error.description)
        flash('La sesión del formulario expiró o no es válida. Intente nuevamente.', 'danger')
        return redirect(request.referrer or url_for('main.index')), 302

    @app.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template(
            'error.html',
            codigo=404,
            titulo='Página no encontrada',
            mensaje='La dirección solicitada no existe o fue movida.',
        ), 404

    @app.errorhandler(500)
    def error_interno(error):
        db.session.rollback()
        app.logger.exception('Error interno no controlado')
        return render_template(
            'error.html',
            codigo=500,
            titulo='Error interno',
            mensaje='Ocurrió un error inesperado. Intente nuevamente o contacte al administrador.',
        ), 500

    # Crear las tablas automáticamente si no existen (SQLite y PostgreSQL).
    # create_all es idempotente: no toca las tablas que ya existen.
    # Los usuarios por defecto solo se crean cuando la BD está vacía y en desarrollo.
    with app.app_context():
        db.create_all()
        _asegurar_columnas_nuevas(app)
        crear_usuarios_defecto(app)

    return app


# Instancia de aplicación para servidores WSGI como Gunicorn (`app:app`)
app = create_app()

__all__ = ['create_app', 'app', 'db', 'Usuario']
