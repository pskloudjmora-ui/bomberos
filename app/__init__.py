from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
from app.models import db, Usuario

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializar base de datos y extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Registrar Blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.reportes import reportes_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(reportes_bp, url_prefix='/reportes')

    # Crear base de datos de forma automática en desarrollo (si es SQLite)
    # o crear tablas si no existen para agilizar el arranque
    with app.app_context():
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            db.create_all()
            # Crear administrador de prueba si no existe
            crear_usuarios_defecto()
            
    return app

# Instancia de aplicación para servidores WSGI como Gunicorn
app = create_app()

__all__ = ['create_app', 'app', 'db', 'Usuario']

def crear_usuarios_defecto():
    """Crea usuarios semilla para pruebas iniciales."""
    # Verificar si ya existen usuarios
    if Usuario.query.first() is None:
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
        print("Usuarios por defecto creados: admin/admin123 y bombero/bombero123")
